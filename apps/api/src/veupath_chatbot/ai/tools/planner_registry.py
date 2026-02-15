"""Planner-mode tool registration mixin.

This module is imported by `PathfinderPlannerAgent` to expose a *restricted*
tool surface appropriate for planning mode (no graph mutation by default).

Keep the module import side-effect free (no instantiation at import time).

Tool results may include special keys that are translated into SSE events:
- `citations`: emitted as a citations event and attached to the assistant message
- `planningArtifact`: emitted and persisted on the plan session
- `conversationTitle`: emitted as a plan_update and persisted as the conversation title
- `reasoning`: emitted and persisted into the thinking payload
"""

from __future__ import annotations

import json
from datetime import UTC
from typing import Annotated, cast

from kani import AIParam, ai_function

from veupath_chatbot.ai.tools.catalog_rag_tools import CatalogRagTools
from veupath_chatbot.ai.tools.catalog_tools import CatalogTools
from veupath_chatbot.ai.tools.query_validation import (
    record_type_query_error,
    search_query_error,
)
from veupath_chatbot.ai.tools.research_registry import ResearchToolsMixin
from veupath_chatbot.platform.types import JSONArray, JSONObject, JSONValue
from veupath_chatbot.services.control_tests import (
    ControlValueFormat,
    run_positive_negative_controls,
)
from veupath_chatbot.services.gene_lookup import (
    lookup_genes_by_text,
    resolve_gene_ids,
)
from veupath_chatbot.services.parameter_optimization import (
    OptimizationConfig,
    ParameterSpec,
)
from veupath_chatbot.services.parameter_optimization import (
    optimize_search_parameters as _run_optimization,
)
from veupath_chatbot.services.parameter_optimization import (
    result_to_json as _opt_result_to_json,
)


class PlannerToolRegistryMixin(ResearchToolsMixin):
    """Kani tool registry for planning-mode agents.

    Inherits ``web_search`` and ``literature_search`` from
    :class:`ResearchToolsMixin`.

    The attributes ``site_id``, ``catalog_tools``, and ``catalog_rag_tools``
    are provided by :class:`PathfinderPlannerAgent`.

    Subclasses (e.g. PathfinderPlannerAgent) must provide :meth:`_emit_event`
    for streaming progress during optimize_search_parameters.
    """

    site_id: str
    catalog_tools: CatalogTools
    catalog_rag_tools: CatalogRagTools

    async def _emit_event(self, event: JSONObject) -> None:
        """Emit an SSE event. Override in subclass to push to streaming queue."""
        pass

    def _combined_result(
        self,
        *,
        rag: JSONValue,
        wdk: JSONValue,
        rag_note: str | None = None,
        wdk_note: str | None = None,
    ) -> JSONObject:
        """Build combined RAG+WDK result, mirroring executor tool shape for consistency."""
        return {
            "rag": {"data": rag, "note": rag_note or ""},
            "wdk": {"data": wdk, "note": wdk_note or ""},
        }

    @ai_function()
    async def list_sites(self) -> JSONObject:
        """List all available VEuPathDB sites (authoritative live list)."""
        sites = await self.catalog_tools.list_sites()
        return self._combined_result(
            rag=[],
            wdk=sites,
            rag_note="No RAG source for sites list.",
            wdk_note="Authoritative list of configured sites.",
        )

    @ai_function()
    async def get_record_types(
        self,
        query: Annotated[
            str | None,
            AIParam(
                desc="Optional semantic query. Must include 2+ specific keywords; one-word/vague queries are rejected."
            ),
        ] = None,
        limit: Annotated[int, AIParam(desc="Max number of results to return")] = 20,
    ) -> JSONObject:
        """Get available record types for the current site (returns both RAG and live WDK)."""
        q = (query or "").strip()
        err = record_type_query_error(q) if q else None
        if err is not None:
            return self._combined_result(
                rag=[],
                wdk=[],
                rag_note=f"Rejected vague query: {err.get('message')}",
                wdk_note="Skipped live WDK record types list to avoid large irrelevant output; refine the query.",
            )
        rag = await self.catalog_rag_tools.rag_get_record_types(q or None, limit)
        wdk = None if q else await self.catalog_tools.get_record_types(self.site_id)
        return self._combined_result(
            rag=rag,
            wdk=wdk,
            rag_note="Qdrant semantic retrieval (requires a specific multi-keyword query; results include score and are thresholded).",
            wdk_note=(
                "Live WDK record types list (authoritative)."
                if not q
                else "Suppressed for query-based call; use RAG results or call get_record_types(query=None) to list all."
            ),
        )

    @ai_function()
    async def list_searches(
        self,
        record_type: Annotated[str, AIParam(desc="Record type to list searches for")],
    ) -> JSONObject:
        """List available searches for a record type on the current site (authoritative live list)."""
        wdk = await self.catalog_tools.list_searches(self.site_id, record_type)
        return self._combined_result(
            rag=[],
            wdk=wdk,
            rag_note="Not applicable: Qdrant retrieval is query-driven; use search_for_searches(query, record_type=...) for RAG.",
            wdk_note="Live WDK searches list for record type (authoritative).",
        )

    @ai_function()
    async def search_for_searches(
        self,
        query: Annotated[
            str,
            AIParam(
                desc="Semantic query to find relevant searches. Must include 2+ specific keywords; one-word/vague queries are rejected."
            ),
        ],
        record_type: Annotated[
            str | None, AIParam(desc="Optional record type to restrict the search")
        ] = None,
        limit: Annotated[int, AIParam(desc="Max number of results to return")] = 20,
    ) -> JSONObject:
        """Find searches matching a query term (returns both RAG and live WDK)."""
        err = search_query_error(query)
        if err is not None:
            return self._combined_result(
                rag=[],
                wdk=[],
                rag_note=f"Rejected vague query: {err.get('message')}",
                wdk_note="Skipped live WDK search to avoid large irrelevant output; refine the query.",
            )
        rag = await self.catalog_rag_tools.rag_search_for_searches(
            query, record_type, limit
        )
        wdk = await self.catalog_tools.search_for_searches(self.site_id, query)
        return self._combined_result(
            rag=rag,
            wdk=wdk,
            rag_note="Qdrant semantic retrieval (fast, may be stale; results include score and are thresholded).",
            wdk_note="Live WDK-backed keyword-ish search across catalog (authoritative).",
        )

    @ai_function()
    async def get_search_parameters(
        self,
        record_type: Annotated[str, AIParam(desc="Record type that owns the search")],
        search_name: Annotated[str, AIParam(desc="WDK search/question urlSegment")],
    ) -> JSONObject:
        """Get detailed parameter info for a search (returns both RAG and live WDK)."""
        rag = await self.catalog_rag_tools.rag_get_search_metadata(
            record_type, search_name
        )
        wdk = await self.catalog_tools.get_search_parameters(
            self.site_id, record_type, search_name
        )
        return self._combined_result(
            rag=rag,
            wdk=wdk,
            rag_note="Qdrant cached search metadata (may be stale / incomplete if ingestion failed).",
            wdk_note="Live WDK expanded search details (authoritative when it succeeds).",
        )

    @ai_function()
    async def save_planning_artifact(
        self,
        title: Annotated[str, AIParam(desc="Short title for the plan")],
        summary_markdown: Annotated[
            str,
            AIParam(desc="Main planning output in markdown (actionable, structured)"),
        ],
        assumptions: Annotated[
            list[str] | None, AIParam(desc="Optional list of assumptions/constraints")
        ] = None,
        parameters: Annotated[
            JSONObject | None,
            AIParam(desc="Chosen/considered parameters (free-form JSON)"),
        ] = None,
        proposed_strategy_plan: Annotated[
            JSONObject | None,
            AIParam(
                desc=(
                    "Optional future strategy plan payload. This is NOT executed in planning mode; "
                    "it can be applied later in execution mode."
                )
            ),
        ] = None,
    ) -> JSONObject:
        """Publish a reusable planning artifact (persisted to the current plan session)."""
        from datetime import datetime
        from uuid import uuid4

        artifact: JSONObject = {
            "id": f"plan_{uuid4().hex[:12]}",
            "title": (title or "").strip() or "New Conversation",
            "summaryMarkdown": summary_markdown or "",
            "assumptions": cast(JSONArray, assumptions or []),
            "parameters": cast(JSONObject, parameters or {}),
            "proposedStrategyPlan": proposed_strategy_plan,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        return {"planningArtifact": artifact}

    @ai_function()
    async def save_delegation_plan_draft(
        self,
        delegation_goal: Annotated[
            str,
            AIParam(
                desc=(
                    "Goal for the delegation plan (what the executor should build). "
                    "This is saved as a draft object the user can review while planning."
                )
            ),
        ],
        delegation_plan: Annotated[
            JSONObject | None,
            AIParam(
                desc=(
                    "Nested delegation plan tree (task/combine nodes). "
                    "May include per-task `context` for required parameters."
                )
            ),
        ] = None,
        notes_markdown: Annotated[
            str | None,
            AIParam(desc="Optional short notes about unresolved decisions / TODOs."),
        ] = None,
    ) -> JSONObject:
        """Save/update a draft delegation plan object on the plan session.

        If ``delegation_plan`` is omitted but ``notes_markdown`` contains a JSON
        object, it is extracted (common model failure: paste JSON into notes but
        omit delegation_plan).
        """
        from datetime import datetime

        from veupath_chatbot.platform.parsing import parse_jsonish

        plan_obj: JSONObject | None = delegation_plan
        if plan_obj is None and isinstance(notes_markdown, str) and notes_markdown:
            start = notes_markdown.find("{")
            end = notes_markdown.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = parse_jsonish(notes_markdown[start : end + 1])
                if isinstance(parsed, dict):
                    plan_obj = parsed

        if plan_obj is None or not isinstance(plan_obj, dict) or not plan_obj:
            return {
                "ok": False,
                "error": "delegation_plan_required",
                "message": (
                    "Missing delegation_plan. Pass the delegation plan JSON as the "
                    "`delegation_plan` argument (a JSON object), not only inside notes_markdown."
                ),
            }

        artifact: JSONObject = {
            "id": "delegation_draft",
            "title": "Delegation plan (draft)",
            "summaryMarkdown": notes_markdown or "",
            "assumptions": [],
            "parameters": cast(
                JSONObject,
                {
                    "delegationGoal": (delegation_goal or "").strip(),
                    "delegationPlan": plan_obj,
                },
            ),
            "proposedStrategyPlan": None,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        return {"planningArtifact": artifact}

    @ai_function()
    async def request_executor_build(
        self,
        delegation_goal: Annotated[str, AIParam(desc="Delegation goal")],
        delegation_plan: Annotated[
            JSONObject | None,
            AIParam(
                desc=(
                    "Delegation plan JSON tree. If omitted, the tool will attempt to load the "
                    "latest saved draft from this plan session (artifact id 'delegation_draft')."
                )
            ),
        ] = None,
        additional_instructions: Annotated[
            str | None,
            AIParam(desc="Optional extra instructions for the executor agent"),
        ] = None,
        delegation_plan_artifact_id: Annotated[
            str | None,
            AIParam(
                desc=(
                    "Optional artifact id to load delegation plan from when delegation_plan is omitted. "
                    "Defaults to 'delegation_draft'."
                )
            ),
        ] = None,
    ) -> JSONObject:
        """Ask the UI to open executor mode and prefill a build message.

        Delegation plan JSON is emitted in a plain fenced block (no language) to
        avoid syntax highlighting in the UI.
        """
        import json

        goal = (delegation_goal or "").strip()
        plan: JSONObject | None = delegation_plan
        loaded_from: str | None = None

        if plan is None:
            getter = getattr(self, "get_plan_session_artifacts", None)
            if getter is not None:
                aid = (delegation_plan_artifact_id or "").strip() or "delegation_draft"
                artifacts = await getter()
                for a in artifacts or []:
                    if not isinstance(a, dict):
                        continue
                    if a.get("id") != aid:
                        continue
                    params = (
                        a.get("parameters")
                        if isinstance(a.get("parameters"), dict)
                        else {}
                    )
                    candidate = (
                        params.get("delegationPlan")
                        if isinstance(params, dict)
                        else None
                    )
                    if isinstance(candidate, dict) and candidate:
                        plan = candidate
                        loaded_from = aid
                        break

        if plan is None or not isinstance(plan, dict) or not plan:
            return {
                "ok": False,
                "error": "delegation_plan_required",
                "message": (
                    "Missing delegation_plan, and no saved delegation draft was found. "
                    "Either pass delegation_plan explicitly, or save a draft with save_delegation_plan_draft first."
                ),
            }

        plan_json = json.dumps(plan, ensure_ascii=True, indent=2, sort_keys=True)
        msg = (
            "Build this strategy using delegation.\n\n"
            "You MUST call `delegate_strategy_subtasks(goal, plan)` with the JSON below.\n"
            "Use any per-task `context` fields as required parameters/constraints.\n\n"
            f"Goal:\n{goal}\n\n"
            "Delegation plan (JSON):\n"
            f"```\n{plan_json}\n```\n"
        )
        if additional_instructions and str(additional_instructions).strip():
            msg += (
                "\nAdditional instructions:\n"
                + str(additional_instructions).strip()
                + "\n"
            )
        return {
            "executorBuildRequest": {
                "siteId": getattr(self, "site_id", None),
                "message": msg,
                "delegationGoal": goal,
                "delegationPlan": plan,
                "delegationPlanArtifactId": loaded_from,
            }
        }

    @ai_function()
    async def list_saved_planning_artifacts(
        self,
        include_full: Annotated[
            bool,
            AIParam(
                desc=(
                    "If true, return full artifact objects (can be large). "
                    "If false (default), return a compact list (id/title/createdAt)."
                )
            ),
        ] = False,
        limit: Annotated[int, AIParam(desc="Max artifacts to return")] = 50,
    ) -> JSONObject:
        """List planning artifacts already saved on this plan session."""
        getter = getattr(self, "get_plan_session_artifacts", None)
        if getter is None:
            return {
                "ok": False,
                "error": "plan_session_artifacts_unavailable",
                "message": "Plan session artifact lookup is not available in this runtime.",
            }
        artifacts = await getter()
        items = [a for a in (artifacts or []) if isinstance(a, dict)]
        items = items[-max(int(limit), 1) :]
        if include_full:
            return {"ok": True, "artifacts": cast(JSONArray, items)}
        compact: JSONArray = [
            cast(
                JSONObject,
                {
                    "id": a.get("id"),
                    "title": a.get("title"),
                    "createdAt": a.get("createdAt"),
                },
            )
            for a in items
        ]
        return {"ok": True, "artifacts": compact}

    @ai_function()
    async def get_saved_planning_artifact(
        self,
        artifact_id: Annotated[
            str, AIParam(desc="Artifact id to fetch (e.g. 'delegation_draft')")
        ],
    ) -> JSONObject:
        """Fetch one previously saved planning artifact by id."""
        getter = getattr(self, "get_plan_session_artifacts", None)
        if getter is None:
            return {
                "ok": False,
                "error": "plan_session_artifacts_unavailable",
                "message": "Plan session artifact lookup is not available in this runtime.",
            }
        aid = (artifact_id or "").strip()
        if not aid:
            return {"ok": False, "error": "artifact_id_required"}
        artifacts = await getter()
        for a in artifacts or []:
            if isinstance(a, dict) and a.get("id") == aid:
                return {"ok": True, "artifact": a}
        return {"ok": False, "error": "artifact_not_found", "artifactId": aid}

    @ai_function()
    async def set_conversation_title(
        self,
        title: Annotated[str, AIParam(desc="Short conversation title")],
    ) -> JSONObject:
        """Update the conversation title (persisted via SSE plan_update)."""
        t = (title or "").strip()
        if not t:
            return {"error": "title_required"}
        return {"conversationTitle": t}

    @ai_function()
    async def report_reasoning(
        self,
        reasoning: Annotated[
            str, AIParam(desc="Model reasoning text to show in Thinking tab")
        ],
    ) -> JSONObject:
        """Publish reasoning text to the Thinking tab for planning mode."""
        r = (reasoning or "").strip()
        if not r:
            return {"error": "reasoning_required"}
        return {"reasoning": r}

    @ai_function()
    async def run_control_tests(
        self,
        record_type: Annotated[str, AIParam(desc="WDK record type (e.g. 'gene')")],
        target_search_name: Annotated[
            str, AIParam(desc="WDK search/question urlSegment")
        ],
        target_parameters: Annotated[
            JSONObject, AIParam(desc="Target search parameter mapping")
        ],
        controls_search_name: Annotated[
            str,
            AIParam(
                desc=(
                    "Search name that can take a list of record IDs (for positive/negative controls)."
                )
            ),
        ],
        controls_param_name: Annotated[
            str,
            AIParam(desc="Parameter name within controls_search_name that accepts IDs"),
        ],
        positive_controls: Annotated[
            list[str] | None, AIParam(desc="Known-positive IDs that should be returned")
        ] = None,
        negative_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-negative IDs that should NOT be returned"),
        ] = None,
        controls_value_format: Annotated[
            ControlValueFormat,
            AIParam(desc="How to encode ID list for the controls parameter"),
        ] = "newline",
        controls_extra_parameters: Annotated[
            JSONObject | None,
            AIParam(desc="Extra fixed parameters for the controls search"),
        ] = None,
        id_field: Annotated[
            str | None,
            AIParam(
                desc=(
                    "Optional record-id field name to extract from answer records "
                    "(varies by site/record type)."
                )
            ),
        ] = None,
    ) -> JSONObject:
        """Run positive and negative control tests using live WDK (temporary internal strategy)."""
        return await run_positive_negative_controls(
            site_id=self.site_id,
            record_type=record_type,
            target_search_name=target_search_name,
            target_parameters=target_parameters or {},
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
            controls_value_format=controls_value_format,
            controls_extra_parameters=controls_extra_parameters,
            id_field=id_field,
        )

    @ai_function()
    async def lookup_gene_records(
        self,
        query: Annotated[
            str,
            AIParam(
                desc=(
                    "Free-text query to search for gene records — gene name, symbol, "
                    "locus tag, product description, or keyword (e.g. 'PfAP2-G', "
                    "'gametocyte surface antigen', 'Pfs25')."
                )
            ),
        ],
        record_type: Annotated[
            str | None,
            AIParam(
                desc=(
                    "Document type filter for site-search (default 'gene'). "
                    "Use 'gene' for most lookups."
                )
            ),
        ] = None,
        limit: Annotated[int, AIParam(desc="Max results to return (default 10)")] = 10,
    ) -> JSONObject:
        """Look up gene records by name, symbol, or description using VEuPathDB site-search.

        Use this to resolve human-readable gene names (from literature or user input)
        to VEuPathDB gene IDs.  The returned IDs can then be used as positive/negative
        controls in `run_control_tests` or `optimize_search_parameters`.
        """
        return await lookup_genes_by_text(
            self.site_id,
            query,
            record_type=record_type,
            limit=max(1, min(limit, 50)),
        )

    @ai_function()
    async def resolve_gene_ids_to_records(
        self,
        gene_ids: Annotated[
            list[str],
            AIParam(
                desc=(
                    "List of gene/locus tag IDs to resolve (e.g. "
                    "['PF3D7_1222600', 'PF3D7_1031000'])."
                )
            ),
        ],
        record_type: Annotated[
            str, AIParam(desc="WDK record type (default 'transcript')")
        ] = "transcript",
        search_name: Annotated[
            str,
            AIParam(desc="WDK search that accepts ID lists (default 'GeneByLocusTag')"),
        ] = "GeneByLocusTag",
        param_name: Annotated[
            str,
            AIParam(desc="Parameter name for the ID list (default 'ds_gene_ids')"),
        ] = "ds_gene_ids",
    ) -> JSONObject:
        """Resolve known gene IDs to full records (product name, organism, gene type).

        Use this to validate gene IDs or fetch metadata for IDs you already have
        (e.g. from literature).  For discovering genes by name, use `lookup_gene_records` instead.
        """
        ids = [str(x).strip() for x in (gene_ids or []) if str(x).strip()]
        if not ids:
            return {"records": [], "totalCount": 0, "error": "No gene IDs provided."}
        if len(ids) > 200:
            return {
                "records": [],
                "totalCount": 0,
                "error": "Too many IDs (max 200). Reduce the list.",
            }
        return await resolve_gene_ids(
            self.site_id,
            ids,
            record_type=record_type,
            search_name=search_name,
            param_name=param_name,
        )

    @ai_function()
    async def optimize_search_parameters(
        self,
        record_type: Annotated[str, AIParam(desc="WDK record type (e.g. 'gene')")],
        search_name: Annotated[
            str, AIParam(desc="WDK search/question urlSegment to optimise")
        ],
        parameter_space_json: Annotated[
            str,
            AIParam(
                desc=(
                    "JSON array of parameters to optimise. Each entry is an object: "
                    '{"name": "<paramName>", "type": "numeric"|"integer"|"categorical", '
                    '"min": <number>, "max": <number>, "logScale"?: bool, "step"?: <number>, "choices"?: ["a","b"]}. '
                    "Example: "
                    '[{"name":"fold_change","type":"numeric","min":1.5,"max":20}]'
                )
            ),
        ],
        fixed_parameters_json: Annotated[
            str,
            AIParam(
                desc=(
                    "JSON object of parameters held constant during optimisation. "
                    'Example: {"organism":"P. falciparum 3D7","direction":"up-regulated"}'
                )
            ),
        ],
        controls_search_name: Annotated[
            str,
            AIParam(desc="Search that accepts a list of record IDs (for controls)"),
        ],
        controls_param_name: Annotated[
            str,
            AIParam(desc="Parameter name within controls_search_name that accepts IDs"),
        ],
        positive_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-positive IDs that should be returned"),
        ] = None,
        negative_controls: Annotated[
            list[str] | None,
            AIParam(desc="Known-negative IDs that should NOT be returned"),
        ] = None,
        budget: Annotated[int, AIParam(desc="Max number of trials (default 30)")] = 30,
        objective: Annotated[
            str,
            AIParam(
                desc=(
                    "Scoring objective: 'f1' (balanced, default), 'recall', "
                    "'precision', 'f_beta' (specify beta), or 'custom'"
                )
            ),
        ] = "f1",
        beta: Annotated[
            float, AIParam(desc="Beta value for f_beta objective (default 1.0)")
        ] = 1.0,
        method: Annotated[
            str,
            AIParam(
                desc="Optimisation method: 'bayesian' (default, recommended), 'grid', or 'random'"
            ),
        ] = "bayesian",
        controls_value_format: Annotated[
            ControlValueFormat,
            AIParam(desc="How to encode the control ID list"),
        ] = "newline",
        controls_extra_parameters_json: Annotated[
            str | None,
            AIParam(
                desc="JSON object of extra fixed parameters for the controls search"
            ),
        ] = None,
        id_field: Annotated[
            str | None,
            AIParam(desc="Optional record-id field name for answer records"),
        ] = None,
        result_count_penalty: Annotated[
            float,
            AIParam(
                desc=(
                    "Weight for penalising large result sets (0 = off, 0.1 = tiebreaker, "
                    "higher = strongly prefer tighter results). Default 0.1."
                )
            ),
        ] = 0.1,
    ) -> str:
        """Optimise search parameters against positive/negative control gene lists.

        Runs multiple trials, varying the parameters in `parameter_space` while
        holding `fixed_parameters` constant. Each trial evaluates the search
        against the controls and scores the result. Returns the best
        configuration, all trials, Pareto frontier, and sensitivity analysis.

        This is a long-running operation. The user will see real-time progress
        in the UI. Always confirm the plan with the user before calling this.
        """
        try:
            raw_space = json.loads(parameter_space_json)
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps(
                {"error": f"parameter_space_json is not valid JSON: {exc}"}
            )

        if not isinstance(raw_space, list):
            return json.dumps({"error": "parameter_space_json must be a JSON array"})

        try:
            fixed_parameters: JSONObject = (
                json.loads(fixed_parameters_json) if fixed_parameters_json else {}
            )
        except (json.JSONDecodeError, TypeError) as exc:
            return json.dumps(
                {"error": f"fixed_parameters_json is not valid JSON: {exc}"}
            )

        controls_extra_parameters: JSONObject | None = None
        if controls_extra_parameters_json:
            try:
                controls_extra_parameters = json.loads(controls_extra_parameters_json)
            except (json.JSONDecodeError, TypeError) as exc:
                return json.dumps(
                    {
                        "error": f"controls_extra_parameters_json is not valid JSON: {exc}"
                    }
                )

        specs: list[ParameterSpec] = []
        for p in raw_space:
            if not isinstance(p, dict):
                continue
            ptype = str(p.get("type", "numeric"))
            if ptype not in ("numeric", "integer", "categorical"):
                ptype = "numeric"
            specs.append(
                ParameterSpec(
                    name=str(p.get("name", "")),
                    param_type=ptype,  # type: ignore[arg-type]
                    min_value=float(p["min"]) if "min" in p else None,
                    max_value=float(p["max"]) if "max" in p else None,
                    log_scale=bool(p.get("logScale", False)),
                    step=float(p["step"]) if "step" in p else None,
                    choices=(
                        [str(c) for c in p["choices"]]
                        if "choices" in p and isinstance(p["choices"], list)
                        else None
                    ),
                )
            )

        obj = (
            objective
            if objective in ("f1", "f_beta", "recall", "precision", "custom")
            else "f1"
        )
        meth = method if method in ("bayesian", "grid", "random") else "bayesian"

        config = OptimizationConfig(
            budget=max(1, min(budget, 200)),
            objective=obj,  # type: ignore[arg-type]
            beta=beta,
            method=meth,  # type: ignore[arg-type]
            result_count_penalty=max(0.0, result_count_penalty),
        )

        cancel_event = getattr(self, "_cancel_event", None)

        result = await _run_optimization(
            site_id=self.site_id,
            record_type=record_type,
            search_name=search_name,
            fixed_parameters=fixed_parameters,
            parameter_space=specs,
            controls_search_name=controls_search_name,
            controls_param_name=controls_param_name,
            positive_controls=positive_controls,
            negative_controls=negative_controls,
            controls_value_format=controls_value_format,
            controls_extra_parameters=controls_extra_parameters,
            id_field=id_field,
            config=config,
            progress_callback=self._emit_event,
            check_cancelled=(cancel_event.is_set if cancel_event is not None else None),
        )

        return json.dumps(_opt_result_to_json(result))
