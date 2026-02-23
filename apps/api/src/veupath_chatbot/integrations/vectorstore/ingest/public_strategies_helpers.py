from __future__ import annotations

import json

from veupath_chatbot.platform.types import JSONArray, JSONObject

EMBED_TEXT_MAX_CHARS = 20_000
PARAM_VALUE_MAX_CHARS = 300


def backoff_delay_seconds(attempt: int) -> int:
    """Exponential backoff delay (capped).

    Matches the ingest script's prior behavior: min(8, 2 ** (attempt - 1)).

    :param attempt: Retry attempt number (1-based).
    :returns: Delay in seconds.
    """
    return int(min(8, 2 ** (attempt - 1)))


def truncate(s: str, *, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    return s[: max(0, max_chars - 20)] + "…(truncated)"


def iter_compact_steps(step_tree: JSONObject | None) -> JSONArray:
    if not isinstance(step_tree, dict):
        return []
    out: JSONArray = []
    stack = [step_tree]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        out.append(node)
        # WDK stepTree nodes: JsonKeys.PRIMARY_INPUT_STEP, JsonKeys.SECONDARY_INPUT_STEP.
        for k in ("primaryInput", "secondaryInput"):
            child = node.get(k)
            if isinstance(child, dict):
                stack.append(child)
    return out


def embedding_text_for_example(
    *, name: str, description: str, compact: JSONObject
) -> str:
    record_class = str(compact.get("recordClassName") or "")
    step_tree_raw = compact.get("stepTree")
    step_tree: JSONObject | None = (
        step_tree_raw if isinstance(step_tree_raw, dict) else None
    )
    steps = iter_compact_steps(step_tree)
    step_lines: list[str] = []
    for st in steps:
        if not isinstance(st, dict):
            continue
        search_name_raw = st.get("searchName")
        search_name = (
            str(search_name_raw or "").strip() if search_name_raw is not None else ""
        )
        operator_raw = st.get("operator")
        operator = str(operator_raw or "").strip() if operator_raw is not None else ""
        params_raw = st.get("parameters")
        params: JSONObject = params_raw if isinstance(params_raw, dict) else {}
        rendered_params: list[str] = []
        for k, v in list(params.items())[:20]:
            vv = truncate(
                json.dumps(v, ensure_ascii=False), max_chars=PARAM_VALUE_MAX_CHARS
            )
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
    return truncate(text, max_chars=EMBED_TEXT_MAX_CHARS)


def simplify_strategy_details(details: JSONObject) -> JSONObject:
    step_tree = details.get("stepTree") or {}
    steps = details.get("steps") or {}

    def simplify_step_node(node: JSONObject) -> JSONObject:
        # stepTree nodes use JsonKeys.STEP_ID = "stepId".
        sid = str(node.get("stepId") or "")
        step = steps.get(sid) if isinstance(steps, dict) else None
        search_name = None
        display_name = None
        operator = None
        params: JSONObject | None = None
        if isinstance(step, dict):
            # Step objects: JsonKeys.SEARCH_NAME, JsonKeys.DISPLAY_NAME.
            search_name = step.get("searchName")
            display_name = step.get("displayName")
            # Operator is in searchConfig.parameters (key containing "operator").
            search_config_raw = step.get("searchConfig")
            if isinstance(search_config_raw, dict):
                raw_params = search_config_raw.get("parameters")
                if isinstance(raw_params, dict):
                    params = raw_params
                    # Extract boolean operator from parameters.
                    for pkey, pval in raw_params.items():
                        if "operator" in str(pkey).lower() and isinstance(pval, str):
                            operator = pval
                            break

        out: JSONObject = {
            "stepId": sid or None,
            "displayName": display_name or None,
            "searchName": search_name or None,
            "operator": operator,
            "parameters": params or {},
        }
        # WDK stepTree uses "primaryInput" and "secondaryInput".
        for key in ("primaryInput", "secondaryInput"):
            child = node.get(key)
            if isinstance(child, dict):
                out[key] = simplify_step_node(child)
        return out

    root = simplify_step_node(step_tree) if isinstance(step_tree, dict) else None
    return {
        "recordClassName": details.get("recordClassName"),
        "rootStepId": details.get("rootStepId"),
        "stepTree": root,
    }


def full_strategy_payload(details: JSONObject) -> JSONObject:
    return {
        "recordClassName": details.get("recordClassName"),
        "rootStepId": details.get("rootStepId"),
        "stepTree": details.get("stepTree"),
        "steps": details.get("steps"),
    }
