#!/usr/bin/env python3
"""Fix remaining type-as-description docstrings to proper Sphinx format."""

from pathlib import Path

REPLACEMENTS = [
    # (pattern, replacement) - applied per line
    (":param value: JSONValue.", ":param value: Value to process."),
    (":param plan: JSONObject.", ":param plan: Plan or strategy dict."),
    (":param value: JSONValue.", ":param value: Value to process."),
    (":param snapshot: JSONObject.", ":param snapshot: Graph snapshot dict."),
    (":param strategy_id: UUID.", ":param strategy_id: Strategy UUID."),
    (":param plan: JSONObject.", ":param plan: Plan dict."),
    (
        ":param param_specs: list[ParameterSpec].",
        ":param param_specs: Parameter specifications.",
    ),
    (
        ":param study: optuna.Study | None:  (default: None)",
        ":param study: Optuna study (default: None).",
    ),
    (":param trials: list[TrialResult].", ":param trials: Trial results."),
    (":param message: str.", ":param message: Chat message."),
    (":param messages: JSONArray.", ":param messages: Message list."),
    (
        ":param raw_id: str | None | JSONValue.",
        ":param raw_id: Raw ID (str, None, or JSON).",
    ),
    (
        ":param model_override: str | None:  (default: None)",
        ":param model_override: Model ID override (default: None).",
    ),
    (
        ":param persisted_model_id: str | None:  (default: None)",
        ":param persisted_model_id: Persisted model ID (default: None).",
    ),
    (
        ":param provider_override: ModelProvider | None:  (default: None)",
        ":param provider_override: Provider override (default: None).",
    ),
    (
        ":param reasoning_effort: ReasoningEffort | None:  (default: None)",
        ":param reasoning_effort: Reasoning effort (default: None).",
    ),
    (
        ":param rag_note: str | None:  (default: None)",
        ":param rag_note: RAG note (default: None).",
    ),
    (
        ":param wdk_note: str | None:  (default: None)",
        ":param wdk_note: WDK note (default: None).",
    ),
    (
        ":param root_step_id: int | None:  (default: None)",
        ":param root_step_id: Root step ID (default: None).",
    ),
    (
        ":param site_id: str | None:  (default: None)",
        ":param site_id: Site ID (default: None).",
    ),
    (":param site_id: str.", ":param site_id: VEuPathDB site identifier."),
    (":param context: JSONObject.", ":param context: Context dict."),
    (":param params: JSONObject | None.", ":param params: Optional params dict."),
    (":param record_type: str.", ":param record_type: WDK record type."),
    (":param search_name: str.", ":param search_name: WDK search name."),
    (":param value: JSONValue.", ":param value: Value to normalize."),
    (":param op: CombineOp.", ":param op: Combine operator."),
    (":param step_id: str.", ":param step_id: Step identifier."),
    (":param data: JSONObject.", ":param data: Data dict."),
    (":param errors: list[ValidationError].", ":param errors: Validation errors list."),
    (":param strategy: StrategyAST.", ":param strategy: Strategy AST."),
    (":param node: PlanStepNode.", ":param node: Plan step node."),
    (":param path: str.", ":param path: Node path."),
    (
        ":param expected_record_type: str.",
        ":param expected_record_type: Expected record type.",
    ),
    (":param citations: list[JSONObject].", ":param citations: Citation objects."),
    (":param node_list: JSONArray.", ":param node_list: List of nodes."),
    (":param context: JSONValue.", ":param context: Context value."),
    (":param provider: ModelProvider.", ":param provider: Model provider."),
    (
        ":param effort: ReasoningEffort | None.",
        ":param effort: Reasoning effort (default: None).",
    ),
    (":param model_id: str.", ":param model_id: Model identifier."),
    (":param rag: JSONValue.", ":param rag: RAG context."),
    (":param wdk: JSONValue.", ":param wdk: WDK context."),
    (":param results: JSONArray.", ":param results: Results array."),
    (":param strategy_id: int.", ":param strategy_id: WDK strategy ID."),
    (":param mock_client: AsyncMock.", ":param mock_client: Mocked WDK client."),
    (":param db_engine: AsyncEngine.", ":param db_engine: Database engine."),
    (
        ":param session_maker: async_sessionmaker[AsyncSession].",
        ":param session_maker: Async session maker.",
    ),
    (":param veupathdb_token: str.", ":param veupathdb_token: VEuPathDB auth token."),
    (":param item: JSONObject.", ":param item: Item dict."),
    (":param provider: ModelProvider.", ":param provider: Model provider."),
    (":param steps: JSONArray.", ":param steps: Steps array."),
    (":param step_id: str.", ":param step_id: Step ID."),
    (":param updates: JSONObject.", ":param updates: Update payload."),
]


def main():
    src = Path(__file__).parent.parent / "src" / "veupath_chatbot"
    for py in src.rglob("*.py"):
        text = py.read_text()
        original = text
        for old, new in REPLACEMENTS:
            while old in text:
                text = text.replace(old, new, 1)  # Replace one at a time
        if text != original:
            py.write_text(text)
            print(f"Updated {py}")


if __name__ == "__main__":
    main()
