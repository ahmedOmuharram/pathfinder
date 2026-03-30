"""Step creation tools (AI-exposed)."""

from typing import Annotated

from kani import AIParam, ai_function
from pydantic import BaseModel

from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.services.catalog.param_validation import ValidationCallbacks
from veupath_chatbot.services.strategies.engine.helpers import StrategyToolsHelpers
from veupath_chatbot.services.strategies.step_creation import (
    ColocationStepSpec,
    StepSpec,
    create_colocation_step,
    create_step,
)


class StepInputSpec(BaseModel):
    """Optional inputs for binary and transform steps.

    Groups the step-wiring fields into a single parameter so the
    ``create_step`` AI function stays within the six-argument limit.
    """

    primary_input_step_id: Annotated[
        str | None,
        AIParam(desc="Primary input step id"),
    ] = None
    secondary_input_step_id: Annotated[
        str | None,
        AIParam(
            desc="Secondary input step id (requires primary_input_step_id and operator)"
        ),
    ] = None
    operator: Annotated[
        str | None,
        AIParam(
            desc="Set operator for binary steps: INTERSECT, UNION, MINUS, RMINUS. For genomic co-location use create_colocation_step instead."
        ),
    ] = None
    display_name: Annotated[
        str | None,
        AIParam(desc="Optional friendly name for this step"),
    ] = None
    combine_with_step_id: Annotated[
        str | None,
        AIParam(
            desc="Step ID to auto-combine with after creation (keeps graph connected)"
        ),
    ] = None
    combine_operator: Annotated[
        str | None,
        AIParam(
            desc="Operator for auto-combine: INTERSECT (default), UNION, MINUS, RMINUS"
        ),
    ] = None


class StrategyStepOps(StrategyToolsHelpers):
    """Tools that add new steps to a graph."""

    @ai_function()
    async def create_step(
        self,
        search_name: Annotated[
            str | None,
            AIParam(
                desc="WDK question/search name (required unless creating a binary step with operator)"
            ),
        ] = None,
        parameters: Annotated[
            JSONObject | None,
            AIParam(desc="WDK parameters as key-value pairs (optional)"),
        ] = None,
        record_type: Annotated[
            str | None,
            AIParam(
                desc="Record type context (e.g., 'transcript'). Defaults to 'transcript' which covers most VEuPathDB gene searches. If omitted, inferred from graph or discovery."
            ),
        ] = None,
        *,
        inputs: Annotated[
            StepInputSpec | None,
            AIParam(
                desc="Optional inputs for binary/transform steps (primary/secondary inputs, operator, display name, colocation params)"
            ),
        ] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Create a new strategy step.

        Step kind is inferred from structure:
        - leaf step: no inputs
        - unary step: inputs.primary_input_step_id only
        - binary step: inputs.primary_input_step_id + inputs.secondary_input_step_id (+ inputs.operator)
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        inp = inputs or StepInputSpec()
        spec = StepSpec(
            search_name=search_name,
            parameters=parameters,
            record_type=record_type,
            primary_input_step_id=inp.primary_input_step_id,
            secondary_input_step_id=inp.secondary_input_step_id,
            operator=inp.operator,
            display_name=inp.display_name,
            combine_with_step_id=inp.combine_with_step_id,
            combine_operator=inp.combine_operator,
        )
        callbacks = ValidationCallbacks(
            resolve_record_type_for_search=self._find_record_type_for_search,
            find_record_type_hint=self._find_record_type_hint,
            extract_vocab_options=self._extract_vocab_options,
            validation_error_payload=self._validation_error_payload,
        )

        result = await create_step(
            graph=graph,
            site_id=self.session.site_id,
            spec=spec,
            callbacks=callbacks,
        )

        if result.error is not None or result.step is None:
            return (
                result.error
                if result.error is not None
                else self._graph_not_found(graph_id)
            )

        response = self._serialize_step(graph, result.step)
        return self._with_full_graph(graph, response)

    class ColocationSpec(BaseModel):
        """Span logic parameters for genomic co-location.

        All fields are optional with sensible defaults.  region_a/region_b
        control which genomic region to compare: 'exact' uses the feature
        as-is; 'upstream'/'downstream' extend from the feature boundary;
        'custom' lets you set begin/end anchors, directions, and bp offsets.
        """

        operation: Annotated[
            str,
            AIParam(desc="Genomic relation: 'overlaps', 'contains', or 'is contained in'"),
        ] = "overlaps"
        strand: Annotated[
            str,
            AIParam(desc="Strand: 'either strand', 'same strand', or 'opposite strand'"),
        ] = "either strand"
        output: Annotated[
            str,
            AIParam(desc="Which result set to return: 'a' (Set A genes) or 'b' (Set B features)"),
        ] = "a"
        region_a: Annotated[
            str,
            AIParam(desc="Region for Set A: 'exact', 'upstream', 'downstream', or 'custom'. Default 'custom' extends 1kb upstream of gene start."),
        ] = "custom"
        begin_a: Annotated[str, AIParam(desc="Set A begin anchor: 'start' or 'stop'")] = "start"
        begin_direction_a: Annotated[str, AIParam(desc="Set A begin direction: '+' or '-'")] = "-"
        begin_offset_a: Annotated[int, AIParam(desc="Set A begin offset in bp (>= 0). Default 1000 = 1kb upstream.")] = 1000
        end_a: Annotated[str, AIParam(desc="Set A end anchor: 'start' or 'stop'")] = "stop"
        end_direction_a: Annotated[str, AIParam(desc="Set A end direction: '+' or '-'")] = "+"
        end_offset_a: Annotated[int, AIParam(desc="Set A end offset in bp (>= 0)")] = 0
        region_b: Annotated[
            str,
            AIParam(desc="Region for Set B: 'exact', 'upstream', 'downstream', or 'custom'"),
        ] = "exact"
        begin_b: Annotated[str, AIParam(desc="Set B begin anchor: 'start' or 'stop'")] = "start"
        begin_direction_b: Annotated[str, AIParam(desc="Set B begin direction: '+' or '-'")] = "+"
        begin_offset_b: Annotated[int, AIParam(desc="Set B begin offset in bp (>= 0)")] = 0
        end_b: Annotated[str, AIParam(desc="Set B end anchor: 'start' or 'stop'")] = "stop"
        end_direction_b: Annotated[str, AIParam(desc="Set B end direction: '+' or '-'")] = "+"
        end_offset_b: Annotated[int, AIParam(desc="Set B end offset in bp (>= 0)")] = 0

    @ai_function()
    async def create_colocation_step(
        self,
        primary_step_id: Annotated[str, AIParam(desc="Step ID of the gene result set (Set A)")],
        secondary_step_id: Annotated[str, AIParam(desc="Step ID of the feature set to co-locate against (Set B)")],
        *,
        span: Annotated[ColocationSpec | None, AIParam(desc="Span logic parameters (all optional, sensible defaults)")] = None,
        display_name: Annotated[str | None, AIParam(desc="Friendly name for this step")] = None,
        graph_id: Annotated[str | None, AIParam(desc="Graph ID to edit")] = None,
    ) -> JSONObject:
        """Create a genomic co-location step (COLOCATE).

        Finds genes from Set A that overlap or are near features from Set B
        on the same chromosome. Uses GenesBySpanLogic internally.

        Example: find genes (Set A) within 1000bp upstream of a DNA motif (Set B).
        """
        graph = self._get_graph(graph_id)
        if not graph:
            return self._graph_not_found(graph_id)

        callbacks = ValidationCallbacks(
            resolve_record_type_for_search=self._find_record_type_for_search,
            find_record_type_hint=self._find_record_type_hint,
            extract_vocab_options=self._extract_vocab_options,
            validation_error_payload=self._validation_error_payload,
        )

        span_params = (span or self.ColocationSpec()).model_dump()

        result = await create_colocation_step(
            graph=graph,
            site_id=self.session.site_id,
            spec=ColocationStepSpec(
                primary_step_id=primary_step_id,
                secondary_step_id=secondary_step_id,
                colocation_kwargs=span_params,
                display_name=display_name,
            ),
            callbacks=callbacks,
        )

        if result.error is not None or result.step is None:
            return (
                result.error
                if result.error is not None
                else self._graph_not_found(graph_id)
            )

        response = self._serialize_step(graph, result.step)
        return self._with_full_graph(graph, response)
