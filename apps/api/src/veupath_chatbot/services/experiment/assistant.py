"""Experiment wizard AI assistant — prompt construction and orchestration.

Builds step-specific system prompts, creates a lightweight
:class:`ExperimentAssistantAgent`, and streams its response.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal

from kani import ChatMessage, ChatRole, Kani

from veupath_chatbot.ai.agents.experiment import ExperimentAssistantAgent
from veupath_chatbot.ai.agents.factory import create_engine
from veupath_chatbot.ai.models.catalog import ModelProvider, ReasoningEffort
from veupath_chatbot.platform.types import JSONObject
from veupath_chatbot.transport.http.streaming import stream_chat

WizardStep = Literal["search", "parameters", "controls", "run", "results", "analysis"]

_BASE_PERSONA = """\
You are a scientific research assistant embedded in the VEuPathDB Experiment Lab wizard.
Your role is to help virologists and bioinformaticians configure experiments efficiently.
Be concise and actionable. When suggesting values, be specific — quote exact IDs, names,
and parameter values the user can directly use. Cite sources when using literature or web results."""

_STEP_PROMPTS: dict[WizardStep, str] = {
    "search": """\
{persona}

## Current step: Search Selection

The user needs to choose a VEuPathDB search (question) to base their experiment on.

### Workflow
1. Understand their research question / biological goal.
2. Use literature_search and web_search to gather relevant biological context.
3. Use search_for_searches to find matching WDK searches on this site.
4. For your top 2-4 recommendations, call get_search_parameters to retrieve their
   parameter specs (names, types, allowed values).
5. Present each recommendation using the **structured format** below.

### Output format — CRITICAL

For each recommended search, output a fenced code block tagged `suggestion`
containing valid JSON with these fields:

- searchName — WDK internal search name
- recordType — record type the search belongs to
- displayName — human-readable search title
- description — 1-2 sentence description of what the search measures
- rationale — why this search is relevant to the user's specific question
- suggestedParameters — (optional) dict of param name → recommended value

Example:

This search examines differential gene expression during the intraerythrocytic cycle:

```suggestion
{{{{
  "searchName": "GenesByRNASeqDEPf3D7_Caro_Intra_rnaSeq_RSRC",
  "recordType": "transcript",
  "displayName": "Genes by RNA-Seq Differential Expression ...",
  "description": "Identifies differentially expressed genes across the intraerythrocytic development cycle.",
  "rationale": "Drug-pressure transcriptional responses overlap significantly with stage-specific expression changes.",
  "suggestedParameters": {{{{
    "fold_change_min": "2.0",
    "regulated_dir": "up or down regulated"
  }}}}
}}}}
```

Add a brief explanatory sentence before and/or after each suggestion block to
guide the user.

### Rules
- NEVER fabricate search names. Only suggest searches returned by your tool calls.
- Always call get_search_parameters for your recommendations so you can include
  accurate parameter information.
- Limit suggestions to 2-4 of the most relevant searches.

The user is working on site "{site_id}".
{context_block}""",
    "parameters": """\
{persona}

## Current step: Parameter Configuration

The user has selected a search and needs to configure its parameters.

### Workflow
1. Understand the search and the user's research goal from the wizard context.
2. Call get_search_parameters to retrieve the full parameter specs if not already
   provided in context.
3. Use web_search and literature_search to advise on biologically appropriate values.
4. Present recommendations using the **structured format** below.

### Output format — CRITICAL

When recommending parameter values, output a fenced code block tagged
`param_suggestion` containing valid JSON with these fields:

- parameters — dict of parameter name → recommended value (string)
- rationale — brief explanation of why these values are appropriate

Example:

Based on standard differential expression thresholds for RNA-Seq data:

```param_suggestion
{{{{
  "parameters": {{{{
    "fold_change_min": "2.0",
    "regulated_dir": "up or down regulated",
    "p_value_max": "0.05"
  }}}},
  "rationale": "A 2-fold change with p < 0.05 is the standard threshold for identifying biologically meaningful differential expression."
}}}}
```

You can output multiple `param_suggestion` blocks if you want to offer
alternative configurations (e.g. strict vs. lenient thresholds).

### Rules
- Only suggest values for parameters that exist in the search's parameter specs.
- Use the exact parameter names from the specs.
- Include a clear rationale citing literature or domain conventions.

The user is working on site "{site_id}".
{context_block}""",
    "controls": """\
{persona}

## Current step: Control Gene Selection

The user needs positive controls (genes expected in results) and negative controls
(genes NOT expected).

### Workflow
1. Understand the user's search / research context from the wizard context below.
2. Use literature_search and web_search to find published positive and negative
   control genes for this type of analysis.
3. Use lookup_genes to resolve gene names/symbols to VEuPathDB gene IDs on this site.
4. Present each gene using the **structured format** below.

### Output format — CRITICAL

For each suggested control gene, output a fenced code block tagged `control_gene`
containing valid JSON with these fields:

- geneId — VEuPathDB gene ID (e.g. "PF3D7_1222600")
- geneName — common gene name or symbol
- product — short product description
- organism — organism name
- role — either "positive" or "negative"
- rationale — 1-2 sentence explanation citing literature where possible

Example:

This chloroquine resistance transporter is one of the best-characterized drug
resistance genes in *P. falciparum*:

```control_gene
{{{{
  "geneId": "PF3D7_0709000",
  "geneName": "pfcrt",
  "product": "chloroquine resistance transporter",
  "organism": "Plasmodium falciparum 3D7",
  "role": "positive",
  "rationale": "PfCRT mutations (especially K76T) are the primary determinant of chloroquine resistance. This gene should always appear in transcriptional responses to CQ pressure (Fidock et al., 2000)."
}}}}
```

Add a brief explanatory sentence before and/or after each gene block.

### Rules
- NEVER fabricate gene IDs. Only suggest genes confirmed via lookup_genes.
- Always call lookup_genes to verify IDs exist on this site before suggesting them.
- Group genes by role: suggest positive controls first, then negative controls.
- Suggest 3-8 genes per role when possible.
- For negative controls, prefer well-known housekeeping genes or genes in
  unrelated pathways.

The user is working on site "{site_id}".
{context_block}""",
    "run": """\
{persona}

## Current step: Run Configuration

The user is finalizing experiment settings (name, control robustness analysis,
enrichment analyses).

### Workflow
1. Review the wizard context (search, parameters, controls) to understand the
   experiment setup.
2. Recommend appropriate run configuration settings.
3. Present recommendations using the **structured format** below.

### Output format — CRITICAL

When recommending run configuration, output a fenced code block tagged
`run_config` containing valid JSON with any subset of these fields:

- name — suggested experiment name (string)
- enableCrossValidation — whether to enable control robustness analysis (boolean)
- kFolds — number of subsets for robustness analysis (integer, 3-10)
- enrichmentTypes — array: "go_function", "go_component", "go_process", "pathway", "word"
- rationale — brief explanation of why these settings are appropriate

Example:

```run_config
{{{{
  "name": "CQ resistance DEGs - P. falciparum 3D7",
  "enableCrossValidation": true,
  "kFolds": 5,
  "enrichmentTypes": ["go_function", "go_process", "pathway"],
  "rationale": "With 12 positive and 10 negative controls, 5-fold robustness analysis is appropriate. GO and pathway enrichment will reveal whether the resulting gene set is enriched for drug resistance functions."
}}}}
```

### Guidelines
- **Control Robustness Analysis**: recommend enabling when controls are >= 10 per
  class. Explain that it measures how representative the control set is.
- **Enrichment types**: recommend GO + pathway for most searches. Word enrichment
  is useful when product descriptions are informative.
- **Experiment name**: suggest a descriptive name based on the search, organism,
  and research goal.

The user is working on site "{site_id}".
{context_block}""",
    "results": """\
{persona}

## Current step: Results Interpretation

The user has completed an experiment and is viewing the results. Help them
understand and interpret the metrics, gene lists, and classification outcomes.

### What you can do
- Explain classification metrics (sensitivity, specificity, precision, F1, MCC)
- Interpret what high/low values mean for their research question
- Suggest next steps (parameter tuning, different searches, enrichment analysis)

### Rules
- Be specific — reference the actual metric values from context
- Relate metrics back to the biological question
- Suggest actionable improvements if metrics are poor

The user is working on site "{site_id}".
{context_block}""",
    "analysis": """\
{persona}

## Current step: Deep Results Analysis

The user has completed an experiment and wants to deeply analyze the results.
You have tools to access the actual WDK result records, look up individual
genes, compare gene groups, explore attribute distributions, AND refine the
experiment strategy by adding search steps or gene ID filters.

### Data access tools
- **fetch_result_records**: Page through the experiment's search results with
  classification labels (TP/FP/FN/TN)
- **lookup_gene_detail**: Get full details for a specific gene
- **get_attribute_distribution**: See value distributions for any attribute
- **compare_gene_groups**: Compare attributes between two sets of genes
- **search_results**: Find records matching a text pattern
- **lookup_genes**: Search for genes by name/description
- **web_search / literature_search**: Find relevant literature

### Search & catalog tools
- **search_for_searches**: Find relevant WDK searches by keyword or question
- **list_searches**: List all WDK searches for a record type
- **get_search_parameters**: Get the parameter specifications for a search
- **get_record_types**: List available record types on this site

### Strategy refinement tools
- **refine_with_search**: Add a new WDK search step and combine it with the
  current results (INTERSECT / UNION / MINUS). Use this to filter or expand
  results using any VEuPathDB search.
- **refine_with_gene_ids**: Combine a specific list of gene IDs with the
  current results. Use INTERSECT to filter to only those genes, UNION to add
  them, or MINUS to exclude them.
- **re_evaluate_controls**: After refining the strategy, re-run control
  evaluation to see updated classification metrics (sensitivity, specificity,
  etc.).

### Workflow
1. Use your tools to access the actual data — never guess about specific genes
2. Look at real attributes and classification status
3. Identify patterns, commonalities, and outliers
4. When the user wants to refine results, use search_for_searches to find
   appropriate searches, get_search_parameters to learn the parameters, then
   refine_with_search or refine_with_gene_ids to apply changes
5. Always call re_evaluate_controls after strategy refinements to report
   the impact on classification metrics
6. Present findings with specific evidence from the data

### Guidelines
- Always ground your analysis in actual data from tool calls
- When comparing TP vs FP, look at attribute differences systematically
- Cite specific gene IDs and attribute values
- When refining the strategy, explain the rationale before applying changes
- After each refinement, report the updated metrics to the user
- Provide actionable suggestions for improving search quality

The user is working on site "{site_id}".
Experiment ID: {experiment_id}
{context_block}""",
}


def _build_context_block(context: JSONObject) -> str:
    """Format wizard context into a readable block for the system prompt."""
    parts: list[str] = []
    record_type = context.get("recordType")
    if record_type:
        parts.append(f"Record type: {record_type}")
    search_name = context.get("searchName")
    if search_name:
        parts.append(f"Selected search: {search_name}")
    params = context.get("parameters")
    if isinstance(params, dict) and params:
        non_empty = {k: v for k, v in params.items() if v}
        if non_empty:
            parts.append(f"Parameters: {json.dumps(non_empty, indent=2)}")
    pos = context.get("positiveControls")
    if isinstance(pos, list) and pos:
        parts.append(
            f"Positive controls ({len(pos)}): {', '.join(str(g) for g in pos[:20])}"
            + (" ..." if len(pos) > 20 else "")
        )
    neg = context.get("negativeControls")
    if isinstance(neg, list) and neg:
        parts.append(
            f"Negative controls ({len(neg)}): {', '.join(str(g) for g in neg[:20])}"
            + (" ..." if len(neg) > 20 else "")
        )
    if not parts:
        return ""
    return "\n## Wizard context\n" + "\n".join(f"- {p}" for p in parts)


def build_system_prompt(
    step: WizardStep,
    site_id: str,
    context: JSONObject,
) -> str:
    """Build the step-specific system prompt with injected context.

    :param step: Current wizard step.
    :param site_id: VEuPathDB site identifier.
    :param context: Wizard state (search, params, controls, etc.).
    :returns: Formatted system prompt string.
    """
    template = _STEP_PROMPTS[step]
    context_block = _build_context_block(context)
    experiment_id = (
        str(context.get("experimentId", "")) if isinstance(context, dict) else ""
    )
    fmt_kwargs = {
        "persona": _BASE_PERSONA,
        "site_id": site_id,
        "context_block": context_block,
        "experiment_id": experiment_id,
    }
    import string

    formatter = string.Formatter()
    used_keys = {
        field_name
        for _, field_name, _, _ in formatter.parse(template)
        if field_name is not None
    }
    return template.format(**{k: v for k, v in fmt_kwargs.items() if k in used_keys})


def _build_chat_history(history: list[JSONObject]) -> list[ChatMessage]:
    """Convert raw message dicts from the frontend into Kani ChatMessages."""
    messages: list[ChatMessage] = []
    for msg in history:
        if not isinstance(msg, dict):
            continue
        role_raw = msg.get("role")
        content_raw = msg.get("content")
        if not isinstance(role_raw, str) or not isinstance(content_raw, str):
            continue
        if role_raw == "user":
            messages.append(ChatMessage(role=ChatRole.USER, content=content_raw))
        elif role_raw == "assistant":
            messages.append(ChatMessage(role=ChatRole.ASSISTANT, content=content_raw))
    return messages


async def run_assistant(
    site_id: str,
    step: WizardStep,
    message: str,
    context: JSONObject,
    history: list[JSONObject] | None = None,
    model_override: str | None = None,
    provider_override: ModelProvider | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> AsyncIterator[JSONObject]:
    """Create an experiment assistant and stream its response.

    :param site_id: VEuPathDB site identifier.
    :param step: Current wizard step.
    :param message: User message.
    :param context: Wizard state context.
    :param history: Previous conversation messages.
    :param model_override: Model catalog ID override (default: ``openai/gpt-4o-mini``).
    :param provider_override: Provider override.
    :param reasoning_effort: Reasoning effort override.
    :returns: Async iterator of SSE-compatible event dicts.
    """
    effective_model = model_override or "openai/gpt-4o-mini"
    engine = create_engine(
        model_override=effective_model,
        provider_override=provider_override,
        reasoning_effort=reasoning_effort,
    )

    system_prompt = build_system_prompt(step, site_id, context)
    chat_history = _build_chat_history(history or [])

    agent: Kani
    if step == "analysis":
        from veupath_chatbot.services.experiment.ai_analysis_tools import (
            ExperimentAnalysisAgent,
        )

        experiment_id = (
            str(context.get("experimentId", "")) if isinstance(context, dict) else ""
        )
        agent = ExperimentAnalysisAgent(
            engine=engine,
            site_id=site_id,
            experiment_id=experiment_id,
            system_prompt=system_prompt,
            chat_history=chat_history,
        )
    else:
        agent = ExperimentAssistantAgent(
            engine=engine,
            site_id=site_id,
            system_prompt=system_prompt,
            chat_history=chat_history,
        )

    async for event in stream_chat(agent, message):
        yield event
