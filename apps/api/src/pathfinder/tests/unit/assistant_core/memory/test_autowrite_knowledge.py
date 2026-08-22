"""Tests for the autowrite path that turns a verification digest into
knowledge memories. The assertions cover the candidates and their values,
which is what the memory store receives.
"""

from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.state import (
    PhaseDisposition,
    PipelineState,
    StrategyDomainState,
    VerificationDigest,
)
from pathfinder.ai.lead.memory_candidates import collect_memory_candidates
from pathfinder.assistant_core.memory.schemas import MemoryEntryDraft


def _state(*, digest: VerificationDigest | None) -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="find Plasmodium kinases",
        domain=StrategyDomainState(verification_digest=digest),
    )


def _digest(remember: list[MemoryEntryDraft]) -> VerificationDigest:
    return VerificationDigest(
        disposition=PhaseDisposition.DONE,
        prose="Strategy returned 142 Plasmodium kinases — sample records "
        "look correct, GO enrichment confirms kinase activity.",
        reason="verification passed",
        success=True,
        key_findings=["142 hits", "GO:0016301 enrichment p<1e-12"],
        caveats=[],
        remember=remember,
    )


def test_no_remember_yields_no_knowledge_candidates() -> None:
    """A digest with an empty remember list adds no candidate."""
    state = _state(digest=_digest(remember=[]))
    candidates = collect_memory_candidates(state)
    knowledge = [v for v, _key in candidates if v.kind == "knowledge"]
    assert knowledge == []


def test_no_digest_yields_no_knowledge_candidates() -> None:
    """A turn without a digest writes no knowledge memory."""
    state = _state(digest=None)
    candidates = collect_memory_candidates(state)
    knowledge = [v for v, _key in candidates if v.kind == "knowledge"]
    assert knowledge == []


def test_remember_lifts_to_full_memory_value() -> None:
    """A draft becomes a full memory value. The site and the source
    conversation come from pipeline state, not from the model."""
    draft = MemoryEntryDraft(
        name="P. falciparum kinome size",
        summary="P. falciparum 3D7 has ~142 protein kinases by GO:0016301",
        content={
            "organism": "P. falciparum 3D7",
            "go_term": "GO:0016301",
            "count": 142,
            "method": "GenesByGoTerm + transmembrane filter",
        },
        tags=["kinome", "kinase"],
    )
    state = _state(digest=_digest(remember=[draft]))
    candidates = collect_memory_candidates(state)
    knowledge = [v for v, _key in candidates if v.kind == "knowledge"]
    assert len(knowledge) == 1
    mv = knowledge[0]

    assert mv.kind == "knowledge"
    assert mv.name == "P. falciparum kinome size"
    assert mv.summary.startswith("P. falciparum 3D7 has ~142")
    assert mv.content["count"] == 142
    assert mv.content["go_term"] == "GO:0016301"

    assert mv.site_id == "plasmodb"
    assert mv.source_conversation_id == state.conversation_id

    # The draft tags survive, and the site id joins them so retrieval can
    # scope by site.
    assert "kinome" in mv.tags
    assert "kinase" in mv.tags
    assert "plasmodb" in mv.tags


def test_existing_site_tag_not_duplicated() -> None:
    """A draft that already carries the site tag keeps one copy of it."""
    draft = MemoryEntryDraft(
        name="x",
        summary="y",
        content={"k": "v"},
        tags=["plasmodb", "extra"],
    )
    state = _state(digest=_digest(remember=[draft]))
    candidates = collect_memory_candidates(state)
    mv = next(v for v, _ in candidates if v.kind == "knowledge")
    assert mv.tags.count("plasmodb") == 1
    assert "extra" in mv.tags


def test_multiple_drafts_get_distinct_keys() -> None:
    """Each draft gets its own deterministic key, so a repeated write
    updates the memory instead of adding one."""
    drafts = [
        MemoryEntryDraft(
            name=f"finding {i}",
            summary=f"summary {i}",
            content={"i": i},
        )
        for i in range(3)
    ]
    state = _state(digest=_digest(remember=drafts))
    candidates = collect_memory_candidates(state)
    knowledge_keys = [k for v, k in candidates if v.kind == "knowledge"]
    assert len(knowledge_keys) == 3
    assert len(set(knowledge_keys)) == 3
    for idx, key in enumerate(knowledge_keys):
        assert key == f"knowledge:{state.conversation_id.hex}:{idx}"


def test_verification_digest_carries_typed_routing_signal() -> None:
    """The digest carries the routing fields that autowrite and the Lead flow
    control read."""
    digest = _digest(remember=[])
    assert digest.disposition == PhaseDisposition.DONE
    assert isinstance(digest.prose, str)
    assert isinstance(digest.reason, str)
    assert digest.success is True
    assert "142 hits" in digest.key_findings
