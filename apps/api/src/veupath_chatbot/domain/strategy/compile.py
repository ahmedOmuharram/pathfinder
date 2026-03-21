"""Compile strategy AST to WDK API calls."""

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from pydantic import Field

from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import (
    ParamSpecNormalized,
    adapt_param_specs,
    find_input_step_param,
    unwrap_search_data,
)
from veupath_chatbot.domain.strategy.ast import (
    PlanStepNode,
    StepTreeNode,
    StrategyAST,
)
from veupath_chatbot.domain.strategy.ops import CombineOp, get_wdk_operator
from veupath_chatbot.platform.errors import (
    InternalError,
    StrategyCompilationError,
    ValidationError,
)
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.platform.pydantic_base import CamelModel
from veupath_chatbot.platform.types import JSONObject, JSONValue

# Callback type: given a search name, returns the owning record type (or None).
# Mirrors WDK's WdkModel.getQuestionByName() — a global lookup across all
# record types.  Callers inject an implementation backed by the pre-cached
# SearchCatalog so no HTTP calls are needed at compile time.
ResolveRecordType = Callable[[str], Awaitable[str | None]]

# ---------------------------------------------------------------------------
# Protocol: I/O boundary the compiler depends on
# ---------------------------------------------------------------------------


class _CompilerClient(Protocol):
    """Protocol for the WDK HTTP client methods the compiler needs."""

    async def get_search_details(
        self, record_type: str, search_name: str, *, expand_params: bool = False
    ) -> JSONObject: ...

    async def get_search_details_with_params(
        self,
        record_type: str,
        search_name: str,
        context: JSONObject,
        *,
        expand_params: bool = False,
    ) -> JSONObject: ...


@runtime_checkable
class StrategyCompilerAPI(Protocol):
    """I/O boundary for strategy compilation.

    The compiler calls these methods to create WDK steps and datasets.
    Any object that satisfies this protocol can be injected -- the real
    :class:`StrategyAPI` from the integrations layer is one such object.
    """

    @property
    def client(self) -> _CompilerClient: ...

    async def create_step(
        self,
        record_type: str,
        search_name: str,
        parameters: JSONObject,
        custom_name: str | None = None,
        wdk_weight: int | None = None,
    ) -> JSONObject: ...

    async def create_combined_step(
        self,
        primary_step_id: int,
        secondary_step_id: int,
        boolean_operator: str,
        record_type: str,
        custom_name: str | None = None,
        wdk_weight: int | None = None,
    ) -> JSONObject: ...

    async def create_transform_step(
        self,
        input_step_id: int,
        transform_name: str,
        parameters: JSONObject,
        record_type: str = "transcript",
        custom_name: str | None = None,
        wdk_weight: int | None = None,
    ) -> JSONObject: ...

    async def create_dataset(self, ids: list[str]) -> int: ...


@runtime_checkable
class StepDecoratorAPI(Protocol):
    """I/O boundary for post-compilation step decorations (filters, analyses, reports)."""

    async def set_step_filter(
        self,
        step_id: int,
        filter_name: str,
        value: JSONValue,
        *,
        disabled: bool = False,
    ) -> JSONValue: ...

    async def run_step_analysis(
        self,
        step_id: int,
        analysis_type: str,
        parameters: JSONObject | None = None,
        custom_name: str | None = None,
    ) -> JSONObject: ...

    async def run_step_report(
        self, step_id: int, report_name: str, config: JSONObject | None = None
    ) -> JSONValue: ...


logger = get_logger(__name__)


class CompiledStep(CamelModel):
    """A compiled step with WDK step ID."""

    local_id: str
    wdk_step_id: int
    step_type: str = Field(alias="type")
    display_name: str


class CompilationResult(CamelModel):
    """Result of compiling a strategy to WDK."""

    steps: list[CompiledStep]
    step_tree: StepTreeNode
    root_step_id: int


def _extract_wdk_step_id(result: JSONObject) -> int:
    """Extract and validate a numeric WDK step ID from an API response."""
    wdk_step_id_value = result.get("id")
    if not isinstance(wdk_step_id_value, (int, float)):
        msg = f"Expected numeric step ID, got {wdk_step_id_value}"
        raise StrategyCompilationError(msg)
    return int(wdk_step_id_value)


class StrategyCompiler:
    """Compiles strategy AST to WDK API calls."""

    def __init__(
        self,
        api: StrategyCompilerAPI,
        site_id: str | None = None,
        *,
        resolve_record_type: bool = True,
        resolve_search_record_type: ResolveRecordType | None = None,
    ) -> None:
        self.api = api
        self._compiled_steps: dict[str, CompiledStep] = {}
        self.site_id = site_id
        self.resolve_record_type = resolve_record_type
        self._resolve_search_rt = resolve_search_record_type

    async def compile(self, strategy: StrategyAST) -> CompilationResult:
        """Compile strategy to WDK steps and tree.

        This creates all steps via the WDK API and builds
        the step tree structure for creating the strategy.
        """
        logger.info("Compiling strategy", record_type=strategy.record_type)

        self._compiled_steps = {}

        if self.resolve_record_type:
            resolved_record_type = await self._resolve_strategy_record_type(strategy)
            if resolved_record_type and resolved_record_type != strategy.record_type:
                strategy.record_type = resolved_record_type

        # Compile the tree recursively (creates steps bottom-up)
        step_tree = await self._compile_node(strategy.root, strategy.record_type)

        # Get root step ID
        root_step = self._compiled_steps.get(strategy.root.id)
        if not root_step:
            raise InternalError(
                title="Strategy compilation failed",
                detail="Failed to compile root step.",
            )

        return CompilationResult(
            steps=list(self._compiled_steps.values()),
            step_tree=step_tree,
            root_step_id=root_step.wdk_step_id,
        )

    async def _compile_node(self, node: PlanStepNode, record_type: str) -> StepTreeNode:
        """Compile a single node, returning its step tree."""
        kind = node.infer_kind()
        if kind == "search":
            return await self._compile_search(node, record_type)
        if kind == "combine":
            return await self._compile_combine(node, record_type)
        if kind == "transform":
            return await self._compile_transform(node, record_type)
        msg = f"Unknown node kind: {kind}"
        raise StrategyCompilationError(msg)

    async def _resolve_strategy_record_type(self, strategy: StrategyAST) -> str | None:
        """Resolve the strategy-level record type from leaf searches.

        Uses the injected callback to look up each leaf search's record type,
        then returns the common record type if all agree.
        """
        if self._resolve_search_rt is None:
            return None
        search_steps = [
            step.search_name
            for step in strategy.get_all_steps()
            if step.infer_kind() == "search"
        ]
        if not search_steps:
            return None
        resolved_types: set[str] = set()
        for search_name in search_steps:
            rt = await self._resolve_search_rt(search_name)
            if not rt:
                return None
            resolved_types.add(rt)
        if len(resolved_types) == 1:
            return next(iter(resolved_types))
        if len(resolved_types) > 1:
            raise ValidationError(
                title="Strategy mixes record types",
                detail="Searches in this strategy belong to multiple record types and cannot be combined.",
                errors=[
                    {"recordType": record_type}
                    for record_type in sorted(resolved_types)
                ],
            )
        return None

    async def _compile_search(
        self, step: PlanStepNode, record_type: str
    ) -> StepTreeNode:
        """Compile a search step."""
        logger.debug("Compiling search step", step_id=step.id, search=step.search_name)

        search_rt = await self._resolve_search_record_type(
            step.search_name, record_type
        )
        parameters = await self._coerce_parameters(
            search_rt, step.search_name, step.parameters
        )
        result = await self.api.create_step(
            record_type=search_rt,
            search_name=step.search_name,
            parameters=parameters,
            custom_name=step.display_name,
            wdk_weight=step.wdk_weight,
        )
        wdk_step_id = _extract_wdk_step_id(result)

        self._compiled_steps[step.id] = CompiledStep(
            local_id=step.id,
            wdk_step_id=wdk_step_id,
            step_type="search",
            display_name=step.display_name or step.search_name,
        )
        return StepTreeNode(step_id=wdk_step_id)

    async def _compile_combine(
        self, step: PlanStepNode, record_type: str
    ) -> StepTreeNode:
        """Compile a combine step."""
        if not step.primary_input or not step.secondary_input:
            msg = "Combine step missing inputs"
            raise StrategyCompilationError(msg)
        if step.operator is None:
            msg = "Combine step missing operator"
            raise StrategyCompilationError(msg)

        logger.debug("Compiling combine step", step_id=step.id, op=step.operator.value)

        left_tree = await self._compile_node(step.primary_input, record_type)
        right_tree = await self._compile_node(step.secondary_input, record_type)

        if step.operator == CombineOp.COLOCATE:
            result = await self._compile_colocation(
                step, left_tree.step_id, right_tree.step_id, record_type
            )
        else:
            wdk_op = get_wdk_operator(step.operator)
            result = await self.api.create_combined_step(
                primary_step_id=left_tree.step_id,
                secondary_step_id=right_tree.step_id,
                boolean_operator=wdk_op,
                record_type=record_type,
                custom_name=step.display_name,
                wdk_weight=step.wdk_weight,
            )

        wdk_step_id = _extract_wdk_step_id(result)
        self._compiled_steps[step.id] = CompiledStep(
            local_id=step.id,
            wdk_step_id=wdk_step_id,
            step_type="combine",
            display_name=step.display_name or f"{step.operator.value}",
        )
        return StepTreeNode(
            step_id=wdk_step_id, primary_input=left_tree, secondary_input=right_tree
        )

    async def _compile_colocation(
        self,
        step: PlanStepNode,
        left_step_id: int,
        right_step_id: int,
        record_type: str,
    ) -> JSONObject:
        """Compile a colocation operation using WDK's GenesBySpanLogic search.

        GenesBySpanLogic ("Genes by Relative Location") has two ``input-step``
        params (``span_a``, ``span_b``).  WDK requires them to be ``""`` at
        step creation — the actual input wiring happens via the ``stepTree``
        when the strategy is created/updated (``primaryInput`` → ``span_a``,
        ``secondaryInput`` → ``span_b``).

        The ``span_sentence`` param is vestigial but **required** (WDK rejects
        empty); the frontend always sets it to ``"sentence"``.
        """
        logger.debug(
            "Compiling colocation",
            left=left_step_id,
            right=right_step_id,
            upstream=step.colocation_params.upstream if step.colocation_params else 0,
            downstream=step.colocation_params.downstream
            if step.colocation_params
            else 0,
        )
        params: JSONObject = {
            "span_sentence": "sentence",
            "span_operation": "overlap",
            "span_strand": "Both strands",
            "span_output": "a",
            "region_a": "upstream",
            "region_b": "exact",
            "span_begin_a": "start",
            "span_begin_direction_a": "-",
            "span_begin_offset_a": str(
                step.colocation_params.upstream if step.colocation_params else 0
            ),
            "span_end_a": "start",
            "span_end_direction_a": "-",
            "span_end_offset_a": str(
                step.colocation_params.downstream if step.colocation_params else 0
            ),
            "span_begin_b": "start",
            "span_begin_direction_b": "-",
            "span_begin_offset_b": "0",
            "span_end_b": "stop",
            "span_end_direction_b": "-",
            "span_end_offset_b": "0",
        }
        return await self.api.create_transform_step(
            input_step_id=left_step_id,
            transform_name="GenesBySpanLogic",
            parameters=params,
            record_type=record_type,
            custom_name=step.display_name or "Genomic colocation",
            wdk_weight=step.wdk_weight,
        )

    async def _resolve_search_record_type(
        self, search_name: str, default_record_type: str
    ) -> str:
        """Resolve the record type for a search.

        Uses the injected ``resolve_search_record_type`` callback (backed by
        the pre-cached SearchCatalog) which mirrors WDK's global
        ``getQuestionByName()`` lookup.  Falls back to the strategy-level
        default when no callback is available.
        """
        if self._resolve_search_rt is not None:
            resolved = await self._resolve_search_rt(search_name)
            if resolved:
                return resolved
        return default_record_type

    async def _compile_transform(
        self, step: PlanStepNode, record_type: str
    ) -> StepTreeNode:
        """Compile a transform step."""
        if not step.primary_input:
            msg = "Transform step missing primaryInput"
            raise StrategyCompilationError(msg)

        logger.debug(
            "Compiling transform step", step_id=step.id, transform=step.search_name
        )

        input_tree = await self._compile_node(step.primary_input, record_type)
        transform_rt = await self._resolve_search_record_type(
            step.search_name, record_type
        )
        parameters = await self._coerce_parameters(
            transform_rt, step.search_name, step.parameters
        )
        result = await self.api.create_transform_step(
            input_step_id=input_tree.step_id,
            transform_name=step.search_name,
            parameters=parameters,
            record_type=transform_rt,
            custom_name=step.display_name,
            wdk_weight=step.wdk_weight,
        )
        wdk_step_id = _extract_wdk_step_id(result)

        self._compiled_steps[step.id] = CompiledStep(
            local_id=step.id,
            wdk_step_id=wdk_step_id,
            step_type="transform",
            display_name=step.display_name or step.search_name,
        )
        return StepTreeNode(step_id=wdk_step_id, primary_input=input_tree)

    async def _coerce_parameters(
        self, record_type: str, search_name: str, parameters: JSONObject
    ) -> JSONObject:
        specs = await self._load_param_specs(record_type, search_name)
        normalized = await self._normalize_with_context_retry(
            record_type, search_name, parameters or {}, specs
        )

        input_step_param = find_input_step_param(specs)
        if input_step_param:
            normalized[input_step_param] = ""

        await self._upload_raw_datasets(specs, normalized)
        return normalized

    async def _load_param_specs(
        self, record_type: str, search_name: str
    ) -> dict[str, ParamSpecNormalized]:
        """Fetch search metadata from WDK and return adapted param specs."""
        try:
            details = await self.api.client.get_search_details(
                record_type, search_name, expand_params=True
            )
        except Exception as exc:
            raise ValidationError(
                title="Failed to load search metadata",
                detail=f"Unable to load parameter metadata for '{search_name}' ({record_type}).",
                errors=[{"searchName": search_name, "recordType": record_type}],
            ) from exc
        return adapt_param_specs(unwrap_search_data(details) or {})

    async def _normalize_with_context_retry(
        self,
        record_type: str,
        search_name: str,
        parameters: JSONObject,
        specs: dict[str, ParamSpecNormalized],
    ) -> JSONObject:
        """Normalize parameters, retrying with contextParamValues on failure.

        WDK question param metadata can be context-dependent. When validation
        fails, we retry with contextParamValues so dependent vocabularies can
        refresh. If the context POST itself errors (some WDK deployments return
        500), we re-raise the original validation error.
        """
        normalizer = ParameterNormalizer(specs)
        try:
            return normalizer.normalize(parameters)
        except ValidationError as validation_exc:
            try:
                details = await self.api.client.get_search_details_with_params(
                    record_type,
                    search_name,
                    context=parameters,
                    expand_params=True,
                )
            except Exception as exc:
                raise validation_exc from exc
            refreshed_specs = adapt_param_specs(unwrap_search_data(details) or {})
            # Update the caller's specs dict so downstream logic (input-step
            # param detection, dataset upload) uses the refreshed metadata.
            specs.clear()
            specs.update(refreshed_specs)
            return ParameterNormalizer(refreshed_specs).normalize(parameters)

    async def _upload_raw_datasets(
        self,
        specs: dict[str, ParamSpecNormalized],
        normalized: JSONObject,
    ) -> None:
        """Auto-upload datasets for input-dataset params.

        WDK DatasetParam fields expect an integer dataset ID. If the LLM
        provided raw record IDs (e.g. gene locus tags) instead, upload them
        as a transient dataset and swap in the integer ID.
        """
        for param_name, spec in specs.items():
            if spec.param_type != "input-dataset":
                continue
            raw_value = normalized.get(param_name)
            if raw_value is None:
                continue
            str_value = str(raw_value).strip()
            try:
                int(str_value)
                continue  # already a valid dataset ID
            except ValueError, TypeError:
                pass
            ids = [
                tok.strip()
                for tok in str_value.replace("\n", ",").split(",")
                if tok.strip()
            ]
            if not ids:
                continue
            dataset_id = await self.api.create_dataset(ids)
            normalized[param_name] = str(dataset_id)
            logger.info(
                "Uploaded dataset for input-dataset param",
                param=param_name,
                id_count=len(ids),
                dataset_id=dataset_id,
            )


async def apply_step_decorations(
    strategy: StrategyAST,
    compiled_map: dict[str, int],
    api: StepDecoratorAPI,
) -> None:
    """Apply filters, analyses, and reports to compiled WDK steps.

    Post-compilation step: walks the strategy AST and applies any
    declared decorations (filters, analyses, reports) to each step's
    WDK counterpart.
    """
    for step in strategy.get_all_steps():
        wdk_step_id = compiled_map.get(step.id)
        if wdk_step_id is None:
            continue
        for step_filter in step.filters:
            await api.set_step_filter(
                step_id=wdk_step_id,
                filter_name=step_filter.name,
                value=step_filter.value,
                disabled=step_filter.disabled,
            )
        for analysis in step.analyses:
            await api.run_step_analysis(
                step_id=wdk_step_id,
                analysis_type=analysis.analysis_type,
                parameters=analysis.parameters,
                custom_name=analysis.custom_name,
            )
        for report in step.reports:
            await api.run_step_report(
                step_id=wdk_step_id,
                report_name=report.report_name,
                config=report.config,
            )


async def compile_strategy(
    strategy: StrategyAST,
    api: StrategyCompilerAPI,
    site_id: str | None = None,
    *,
    resolve_record_type: bool = True,
    resolve_search_record_type: ResolveRecordType | None = None,
) -> CompilationResult:
    """Compile a strategy AST to WDK."""
    compiler = StrategyCompiler(
        api,
        site_id=site_id,
        resolve_record_type=resolve_record_type,
        resolve_search_record_type=resolve_search_record_type,
    )
    return await compiler.compile(strategy)
