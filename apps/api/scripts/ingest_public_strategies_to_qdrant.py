from __future__ import annotations

import argparse
import asyncio
import json
import os
import traceback
import time
from pathlib import Path
from typing import Any

import httpx

from veupath_chatbot.integrations.veupathdb.site_router import get_site_router
from veupath_chatbot.platform.config import get_settings
from veupath_chatbot.services.embeddings.openai_embeddings import OpenAIEmbeddings, embed_one
from veupath_chatbot.services.vectorstore.collections import EXAMPLE_PLANS_V1
from veupath_chatbot.services.vectorstore.qdrant_store import QdrantStore, point_uuid, sha256_hex, stable_json_dumps


def _now_ts() -> int:
    return int(time.time())


def _write_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


async def _sleep_backoff(attempt: int) -> None:
    # attempt=1 -> 1s, 2 -> 2s, 3 -> 4s, 4 -> 8s (cap)
    delay = min(8, 2 ** (attempt - 1))
    await asyncio.sleep(delay)


# Embedding models have a max input token limit (often ~8191 tokens).
# We keep a conservative char-based cap to avoid embedding request failures.
_EMBED_TEXT_MAX_CHARS = 20_000
_PARAM_VALUE_MAX_CHARS = 300


def _truncate(s: str, *, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    return s[: max(0, max_chars - 20)] + "…(truncated)"


def _iter_compact_steps(step_tree: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(step_tree, dict):
        return []
    out: list[dict[str, Any]] = []
    stack = [step_tree]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        out.append(node)
        for k in ("primaryInput", "secondaryInput", "input"):
            child = node.get(k)
            if isinstance(child, dict):
                stack.append(child)
    return out


def _embedding_text_for_example(*, name: str, description: str, compact: dict[str, Any]) -> str:
    record_class = str(compact.get("recordClassName") or "")
    steps = _iter_compact_steps(compact.get("stepTree"))
    # Summarize step requirements without dumping full JSON.
    step_lines: list[str] = []
    for st in steps:
        search_name = str(st.get("searchName") or "").strip()
        operator = str(st.get("operator") or "").strip()
        params = st.get("parameters") if isinstance(st.get("parameters"), dict) else {}
        # Keep param rendering small.
        rendered_params: list[str] = []
        for k, v in list(params.items())[:20]:
            vv = _truncate(json.dumps(v, ensure_ascii=False), max_chars=_PARAM_VALUE_MAX_CHARS)
            rendered_params.append(f"{k}={vv}")
        params_str = ", ".join(rendered_params)
        line = " - " + " | ".join(x for x in [search_name, operator, params_str] if x)
        if line.strip() != "-":
            step_lines.append(line)

    text = "\n".join(
        [
            name.strip(),
            description.strip(),
            record_class,
            "Searches / operators / params:",
            *step_lines[:50],
        ]
    ).strip()
    return _truncate(text, max_chars=_EMBED_TEXT_MAX_CHARS)


def _simplify_strategy_details(details: dict[str, Any]) -> dict[str, Any]:
    """Extract a stable, compact representation with explicit params per step."""
    step_tree = details.get("stepTree") or {}
    steps = details.get("steps") or {}

    def simplify_step_node(node: dict[str, Any]) -> dict[str, Any]:
        sid = str(node.get("stepId") or node.get("step_id") or "")
        step = steps.get(sid) if isinstance(steps, dict) else None
        # Step details payload shape varies; be defensive.
        search_name = None
        display_name = None
        operator = None
        params: dict[str, Any] | None = None
        if isinstance(step, dict):
            search_name = step.get("searchName") or step.get("questionName")
            display_name = step.get("displayName")
            operator = step.get("operator") or step.get("booleanOperator")
            search_config = step.get("searchConfig") or {}
            if isinstance(search_config, dict):
                raw_params = search_config.get("parameters") or {}
                if isinstance(raw_params, dict):
                    params = raw_params

        out: dict[str, Any] = {
            "stepId": sid or None,
            "displayName": display_name or node.get("displayName") or None,
            "searchName": search_name or node.get("searchName") or None,
            "operator": operator or node.get("operator") or None,
            "parameters": params or {},
        }
        # Children (primary/secondary inputs)
        for key in ("primaryInput", "secondaryInput", "input"):
            child = node.get(key)
            if isinstance(child, dict):
                out[key] = simplify_step_node(child)
        return out

    root = None
    if isinstance(step_tree, dict):
        root = simplify_step_node(step_tree)

    return {
        "recordClassName": details.get("recordClassName"),
        "rootStepId": details.get("rootStepId"),
        "stepTree": root,
    }


def _full_strategy_payload(details: dict[str, Any]) -> dict[str, Any]:
    """Persist the full strategy structure the model can inspect later.

    We keep the original WDK shapes for stepTree + steps, which contain explicit parameters.
    """
    out: dict[str, Any] = {
        "recordClassName": details.get("recordClassName"),
        "rootStepId": details.get("rootStepId"),
        "stepTree": details.get("stepTree"),
        "steps": details.get("steps"),
    }
    return out


async def _generate_name_and_description(
    *, strategy_compact: dict[str, Any], model: str
) -> tuple[str, str]:
    """Generate (name, description) using an LLM. Uses same OpenAI key."""
    settings = get_settings()
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key or None)

    # Keep prompt small-ish but explicit about including params.
    compact_json = json.dumps(strategy_compact, ensure_ascii=False)
    prompt = f"""You are generating metadata for a public strategy example.

Return STRICT JSON with keys:
- name: short, human-friendly title (max 80 chars)
- description: 3-8 sentences. Must be descriptive but MUST NOT be a step-by-step recipe.
  It MUST explicitly include the requirements/criteria represented in the strategy, including:
  - all searches used (searchName)
  - all parameter constraints used for each step (parameters key/value pairs)
  - boolean operators (INTERSECT/UNION/MINUS/RMINUS/COLOCATE) when present

Do not write \"Step 1\", \"Step 2\" or numbered steps.
Do not include markdown.

Strategy (compact JSON):
{compact_json}
"""

    resp = await client.chat.completions.create(
        model=model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("Empty LLM response")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Best-effort extraction if model included extra text.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            raise
    name = str(data.get("name") or "").strip()
    desc = str(data.get("description") or "").strip()
    if not name or not desc:
        raise RuntimeError("LLM returned empty name/description")
    return name, desc


async def _fetch_public_strategy_summaries(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    resp = await client.get("/strategy-lists/public")
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


async def _duplicate_strategy(client: httpx.AsyncClient, signature: str) -> int:
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = await client.post(
                "/users/current/strategies",
                json={"sourceStrategySignature": signature},
                timeout=httpx.Timeout(90.0),
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict) or "id" not in data:
                raise RuntimeError("Unexpected duplicateStrategy response")
            return int(data["id"])
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            await _sleep_backoff(attempt)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            # Retry on transient server errors / throttling.
            if status in (429, 500, 502, 503, 504):
                await _sleep_backoff(attempt)
            else:
                raise
    raise RuntimeError(f"duplicate_strategy failed after retries: {last_exc!r}")


async def _get_strategy_details(client: httpx.AsyncClient, strategy_id: int) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, 6):
        try:
            resp = await client.get(
                f"/users/current/strategies/{strategy_id}",
                timeout=httpx.Timeout(180.0),
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise RuntimeError("Unexpected strategy details response")
            return data
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            await _sleep_backoff(attempt)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            status = exc.response.status_code
            if status in (429, 500, 502, 503, 504):
                await _sleep_backoff(attempt)
            else:
                raise
    raise RuntimeError(f"get_strategy_details failed after retries: {last_exc!r}")


async def _delete_strategy(client: httpx.AsyncClient, strategy_id: int) -> None:
    resp = await client.delete(f"/users/current/strategies/{strategy_id}")
    # best-effort; ignore errors
    if resp.status_code >= 400:
        return


async def ingest_site(
    *,
    site_id: str,
    store: QdrantStore,
    embedder: OpenAIEmbeddings,
    llm_model: str,
    report_path: Path,
    max_strategies: int | None,
    concurrency: int,
) -> None:
    router = get_site_router()
    site = router.get_site(site_id)

    async with httpx.AsyncClient(
        base_url=site.base_url.rstrip("/"),
        timeout=httpx.Timeout(90.0),
        follow_redirects=True,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    ) as client:
        try:
            summaries = await _fetch_public_strategy_summaries(client)
        except Exception as exc:
            _write_jsonl(
                report_path,
                {
                    "ts": _now_ts(),
                    "siteId": site_id,
                    "level": "site",
                    "stage": "fetch_public_strategy_summaries",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            return
        # Filter to plausible “examples”: public + valid + not deleted.
        candidates = [
            s
            for s in summaries
            if s.get("isPublic") is True and s.get("isValid") is True and s.get("isDeleted") is False
        ]
        if max_strategies is not None:
            candidates = candidates[: max(0, int(max_strategies))]
        print(
            f"[examples] site={site_id} public_valid={len(candidates)} total_listed={len(summaries)}",
            flush=True,
        )

        async def flush_batch(points: list[dict[str, Any]], texts: list[str]) -> None:
            if not points:
                return
            # Embeddings can fail if any item exceeds model limits; we pre-truncate but
            # also handle a failure by embedding items individually.
            safe_texts = [_truncate(t, max_chars=_EMBED_TEXT_MAX_CHARS) for t in texts]
            try:
                vectors = await embedder.embed_texts(safe_texts)
            except Exception:
                vectors = []
                for t in safe_texts:
                    # Last-resort: further truncate and embed singly.
                    tt = _truncate(t, max_chars=10_000)
                    vectors.append((await embedder.embed_texts([tt]))[0])
            await store.upsert(
                collection=EXAMPLE_PLANS_V1,
                points=[
                    {"id": p["id"], "vector": v, "payload": p["payload"]}
                    for p, v in zip(points, vectors, strict=True)
                ],
            )
            points.clear()
            texts.clear()

        points: list[dict[str, Any]] = []
        texts: list[str] = []
        attempted = 0
        succeeded = 0
        failed = 0

        sem = asyncio.Semaphore(max(1, int(concurrency)))  # per-site concurrency

        async def process_one(idx: int, summary: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
            nonlocal attempted, succeeded, failed
            signature = str(summary.get("signature") or "").strip()
            if not signature:
                return None
            async with sem:
                attempted += 1
                if idx == 1 or idx % 5 == 0:
                    print(
                        f"[examples] site={site_id} processing {idx}/{len(candidates)} "
                        f"name={str(summary.get('name') or '')[:60]!r}",
                        flush=True,
                    )

                tmp_id: int | None = None
                try:
                    tmp_id = await _duplicate_strategy(client, signature)
                    details = await _get_strategy_details(client, tmp_id)
                except Exception as exc:
                    failed += 1
                    _write_jsonl(
                        report_path,
                        {
                            "ts": _now_ts(),
                            "siteId": site_id,
                            "level": "strategy",
                            "stage": "duplicate_or_fetch_details",
                            "sourceSignature": signature,
                            "sourceStrategyId": summary.get("strategyId"),
                            "error": repr(exc),
                            "traceback": traceback.format_exc(),
                        },
                    )
                    return None
                finally:
                    if tmp_id is not None:
                        await _delete_strategy(client, tmp_id)

                compact = _simplify_strategy_details(details)
                try:
                    gen_name, gen_desc = await _generate_name_and_description(
                        strategy_compact=compact, model=llm_model
                    )
                except Exception:
                    gen_name = str(summary.get("name") or "Public strategy example").strip()
                    gen_desc = str(summary.get("description") or "").strip() or gen_name

                payload: dict[str, Any] = {
                    "siteId": site_id,
                    "sourceSignature": signature,
                    "sourceStrategyId": summary.get("strategyId"),
                    "sourceName": summary.get("name"),
                    "sourceDescription": summary.get("description"),
                    "generatedName": gen_name,
                    "generatedDescription": gen_desc,
                    "recordClassName": summary.get("recordClassName") or compact.get("recordClassName"),
                    "rootStepId": summary.get("rootStepId") or compact.get("rootStepId"),
                    "strategyCompact": compact,
                    "strategyFull": _full_strategy_payload(details),
                    "ingestedAt": int(time.time()),
                }
                payload["sourceHash"] = sha256_hex(stable_json_dumps(payload))

                text = _embedding_text_for_example(
                    name=gen_name,
                    description=gen_desc,
                    compact=compact,
                )
                succeeded += 1
                return payload, text

        tasks = [process_one(i, s) for i, s in enumerate(candidates, start=1)]
        for fut in asyncio.as_completed(tasks):
            res = await fut
            if res is None:
                continue
            payload, text = res
            point_id = point_uuid(f"{site_id}:{payload['sourceSignature']}")
            points.append({"id": point_id, "payload": payload})
            texts.append(text)
            if len(points) >= 10:
                try:
                    await flush_batch(points, texts)
                except Exception as exc:
                    _write_jsonl(
                        report_path,
                        {
                            "ts": _now_ts(),
                            "siteId": site_id,
                            "level": "site",
                            "stage": "qdrant_upsert_batch",
                            "error": repr(exc),
                            "traceback": traceback.format_exc(),
                        },
                    )
                    return

        # Final flush
        try:
            await flush_batch(points, texts)
        except Exception as exc:
            _write_jsonl(
                report_path,
                {
                    "ts": _now_ts(),
                    "siteId": site_id,
                    "level": "site",
                    "stage": "qdrant_upsert_final",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            return

        _write_jsonl(
            report_path,
            {
                "ts": _now_ts(),
                "siteId": site_id,
                "level": "site",
                "stage": "site_complete",
                "candidates": len(candidates),
                "attempted": attempted,
                "succeeded": succeeded,
                "failed": failed,
            },
        )
        if len(candidates) > 0 and succeeded == 0:
            _write_jsonl(
                report_path,
                {
                    "ts": _now_ts(),
                    "siteId": site_id,
                    "level": "site",
                    "stage": "site_failed_all_strategies",
                    "candidates": len(candidates),
                    "attempted": attempted,
                    "failed": failed,
                },
            )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", default="all")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument(
        "--llm-model",
        default="gpt-4o-mini",
        help="Model for generating name/description (uses same OpenAI API key).",
    )
    parser.add_argument(
        "--report-path",
        default="ingest_public_strategies_report.jsonl",
        help="Write failures/progress as JSONL (append-only).",
    )
    parser.add_argument(
        "--max-strategies",
        type=int,
        default=None,
        help="Optional cap per site (useful for debugging).",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        raise SystemExit("openai_api_key is required (embeddings + name/description generation)")

    store = QdrantStore.from_settings()
    dim = len(await embed_one(text="example-plans", model=settings.embeddings_model))

    if args.reset:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(
            url=store.url,
            api_key=store.api_key,
            timeout=store.timeout_seconds,
        )
        if await client.collection_exists(collection_name=EXAMPLE_PLANS_V1):
            await client.delete_collection(collection_name=EXAMPLE_PLANS_V1)

    await store.ensure_collection(name=EXAMPLE_PLANS_V1, vector_size=dim)
    embedder = OpenAIEmbeddings(model=settings.embeddings_model)

    router = get_site_router()
    sites = [s.id for s in router.list_sites()]
    if args.sites != "all":
        wanted = [s.strip() for s in str(args.sites).split(",") if s.strip()]
        sites = [s for s in sites if s in set(wanted)]

    report_path = Path(str(args.report_path))
    _write_jsonl(
        report_path,
        {
            "ts": _now_ts(),
            "level": "run",
            "stage": "start",
            "sites": sites,
            "llmModel": str(args.llm_model),
        },
    )

    concurrency = max(1, int(os.cpu_count() or 1))
    _write_jsonl(
        report_path,
        {
            "ts": _now_ts(),
            "level": "run",
            "stage": "config",
            "concurrency": concurrency,
        },
    )

    for site_id in sites:
        print(f"[examples] site={site_id}", flush=True)
        try:
            await ingest_site(
                site_id=site_id,
                store=store,
                embedder=embedder,
                llm_model=str(args.llm_model),
                report_path=report_path,
                max_strategies=args.max_strategies,
                concurrency=concurrency,
            )
        except Exception as exc:
            # Catch-all so one broken site doesn't abort the entire run.
            _write_jsonl(
                report_path,
                {
                    "ts": _now_ts(),
                    "siteId": site_id,
                    "level": "site",
                    "stage": "unhandled_exception",
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            continue

    _write_jsonl(
        report_path,
        {
            "ts": _now_ts(),
            "level": "run",
            "stage": "end",
        },
    )


if __name__ == "__main__":
    asyncio.run(main())

