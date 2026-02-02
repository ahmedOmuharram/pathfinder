"""Compile strategy AST to WDK API calls."""

from dataclasses import dataclass
from typing import Any

from veupath_chatbot.platform.errors import ValidationError
from veupath_chatbot.platform.logging import get_logger
from veupath_chatbot.domain.parameters.normalize import ParameterNormalizer
from veupath_chatbot.domain.parameters.specs import adapt_param_specs, find_input_step_param
from veupath_chatbot.domain.strategy.ast import (
    CombineStep,
    SearchStep,
    StepNode,
    StrategyAST,
    TransformStep,
)
from veupath_chatbot.domain.strategy.ops import CombineOp, get_wdk_operator
from veupath_chatbot.integrations.veupathdb.strategy_api import StepTreeNode, StrategyAPI

logger = get_logger(__name__)


@dataclass
class CompiledStep:
    """A compiled step with WDK step ID."""

    local_id: str
    wdk_step_id: int
    step_type: str
    display_name: str


@dataclass
class CompilationResult:
    """Result of compiling a strategy to WDK."""

    steps: list[CompiledStep]
    step_tree: StepTreeNode
    root_step_id: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "steps": [
                {
                    "localId": s.local_id,
                    "wdkStepId": s.wdk_step_id,
                    "type": s.step_type,
                    "displayName": s.display_name,
                }
                for s in self.steps
            ],
            "stepTree": self.step_tree.to_dict(),
            "rootStepId": self.root_step_id,
        }


class StrategyCompiler:
    """Compiles strategy AST to WDK API calls."""

    def __init__(
        self,
        api: StrategyAPI,
        site_id: str | None = None,
        resolve_record_type: bool = True,
    ) -> None:
        self.api = api
        self._compiled_steps: dict[str, CompiledStep] = {}
        self.site_id = site_id
        self.resolve_record_type = resolve_record_type
        self._searches_cache: dict[str, list[dict[str, Any]]] = {}

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
            raise RuntimeError("Failed to compile root step")

        return CompilationResult(
            steps=list(self._compiled_steps.values()),
            step_tree=step_tree,
            root_step_id=root_step.wdk_step_id,
        )

    async def _compile_node(self, node: StepNode, record_type: str) -> StepTreeNode:
        """Compile a single node, returning its step tree."""
        if isinstance(node, SearchStep):
            return await self._compile_search(node, record_type)
        if isinstance(node, CombineStep):
            return await self._compile_combine(node, record_type)
        if isinstance(node, TransformStep):
            return await self._compile_transform(node, record_type)
        raise ValueError(f"Unknown node type: {type(node)}")

    async def _resolve_strategy_record_type(self, strategy: StrategyAST) -> str | None:
        record_types = await self._get_record_types()
        if not record_types:
            return None
        search_steps = [
            step.search_name
            for step in strategy.get_all_steps()
            if isinstance(step, SearchStep)
        ]
        if not search_steps:
            return None
        matching_sets: list[set[str]] = []
        for search_name in search_steps:
            matches = await self._get_record_types_for_search(record_types, search_name)
            if not matches:
                return None
            matching_sets.append(matches)
        intersection = set.intersection(*matching_sets)
        if len(intersection) == 1:
            return next(iter(intersection))
        if len(intersection) > 1:
            raise ValidationError(
                title="Strategy mixes record types",
                detail="Searches in this strategy belong to multiple record types and cannot be combined.",
                errors=[
                    {"recordType": record_type} for record_type in sorted(intersection)
                ],
            )
        return None

    async def _get_record_types(self) -> list[dict[str, Any]]:
        try:
            return await self.api.client.get_record_types()
        except Exception:
            return []

    async def _get_record_types_for_search(
        self, record_types: list[dict[str, Any]], search_name: str
    ) -> set[str]:
        matches: set[str] = set()
        for record_type in record_types:
            if isinstance(record_type, str):
                rt_name = record_type
            else:
                rt_name = record_type.get("urlSegment") or record_type.get("name")
            if not rt_name:
                continue
            searches = await self._get_searches_for_record_type(rt_name)
            if any(
                search.get("urlSegment") == search_name or search.get("name") == search_name
                for search in searches
            ):
                matches.add(rt_name)
        return matches

    async def _get_searches_for_record_type(self, record_type: str) -> list[dict[str, Any]]:
        if record_type in self._searches_cache:
            return self._searches_cache[record_type]
        try:
            searches = await self.api.client.get_searches(record_type)
        except Exception:
            searches = []
        self._searches_cache[record_type] = searches
        return searches

    async def _compile_search(self, step: SearchStep, record_type: str) -> StepTreeNode:
        """Compile a search step."""
        logger.debug("Compiling search step", step_id=step.id, search=step.search_name)

        parameters = await self._coerce_parameters(record_type, step.search_name, step.parameters)
        result = await self.api.create_step(
            record_type=record_type,
            search_name=step.search_name,
            parameters=parameters,
            custom_name=step.display_name,
        )
        wdk_step_id = result["id"]

        self._compiled_steps[step.id] = CompiledStep(
            local_id=step.id,
            wdk_step_id=wdk_step_id,
            step_type="search",
            display_name=step.display_name or step.search_name,
        )
        return StepTreeNode(step_id=wdk_step_id)

    async def _compile_combine(self, step: CombineStep, record_type: str) -> StepTreeNode:
        """Compile a combine step."""
        logger.debug("Compiling combine step", step_id=step.id, op=step.op.value)

        left_tree = await self._compile_node(step.left, record_type)
        right_tree = await self._compile_node(step.right, record_type)

        if step.op == CombineOp.COLOCATE:
            result = await self._compile_colocation(step, left_tree.step_id, right_tree.step_id)
        else:
            wdk_op = get_wdk_operator(step.op)
            result = await self.api.create_combined_step(
                primary_step_id=left_tree.step_id,
                secondary_step_id=right_tree.step_id,
                boolean_operator=wdk_op,
                record_type=record_type,
                custom_name=step.display_name,
            )

        wdk_step_id = result["id"]
        self._compiled_steps[step.id] = CompiledStep(
            local_id=step.id,
            wdk_step_id=wdk_step_id,
            step_type="combine",
            display_name=step.display_name or f"{step.op.value}",
        )
        return StepTreeNode(step_id=wdk_step_id, primary_input=left_tree, secondary_input=right_tree)

    async def _compile_colocation(
        self, step: CombineStep, left_step_id: int, right_step_id: int
    ) -> dict[str, Any]:
        """Compile a colocation operation."""
        params: dict[str, Any] = {
            "gene_result": str(left_step_id),
            "span_result": str(right_step_id),
        }
        if step.colocation_params:
            params["upstream"] = str(step.colocation_params.upstream)
            params["downstream"] = str(step.colocation_params.downstream)
            params["strand"] = step.colocation_params.strand
        return await self.api.create_transform_step(
            input_step_id=left_step_id,
            transform_name="GenesByLocation",
            parameters=params,
            custom_name=step.display_name or "Genomic colocation",
        )

    async def _compile_transform(self, step: TransformStep, record_type: str) -> StepTreeNode:
        """Compile a transform step."""
        logger.debug("Compiling transform step", step_id=step.id, transform=step.transform_name)

        input_tree = await self._compile_node(step.input, record_type)
        parameters = await self._coerce_parameters(record_type, step.transform_name, step.parameters)
        result = await self.api.create_transform_step(
            input_step_id=input_tree.step_id,
            transform_name=step.transform_name,
            parameters=parameters,
            custom_name=step.display_name,
        )
        wdk_step_id = result["id"]

        self._compiled_steps[step.id] = CompiledStep(
            local_id=step.id,
            wdk_step_id=wdk_step_id,
            step_type="transform",
            display_name=step.display_name or step.transform_name,
        )
        return StepTreeNode(step_id=wdk_step_id, primary_input=input_tree)

    async def _coerce_parameters(
        self, record_type: str, search_name: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            details = await self.api.client.get_search_details(record_type, search_name, expand_params=True)
        except Exception as exc:
            raise ValidationError(
                title="Failed to load search metadata",
                detail=f"Unable to load parameter metadata for '{search_name}' ({record_type}).",
                errors=[{"searchName": search_name, "recordType": record_type}],
            ) from exc

        if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
            details = details["searchData"]
        specs = adapt_param_specs(details if isinstance(details, dict) else {})
        normalizer = ParameterNormalizer(specs)
        try:
            normalized = normalizer.normalize(parameters or {})
        except ValidationError:
            details = await self.api.client.get_search_details_with_params(
                record_type, search_name, context=parameters or {}, expand_params=True
            )
            if isinstance(details, dict) and isinstance(details.get("searchData"), dict):
                details = details["searchData"]
            specs = adapt_param_specs(details if isinstance(details, dict) else {})
            normalizer = ParameterNormalizer(specs)
            normalized = normalizer.normalize(parameters or {})

        input_step_param = find_input_step_param(specs)
        if input_step_param:
            normalized[input_step_param] = ""
        return normalized


async def compile_strategy(
    strategy: StrategyAST,
    api: StrategyAPI,
    site_id: str | None = None,
    resolve_record_type: bool = True,
) -> CompilationResult:
    """Compile a strategy AST to WDK."""
    compiler = StrategyCompiler(api, site_id=site_id, resolve_record_type=resolve_record_type)
    return await compiler.compile(strategy)

