"""Unit tests for the verification-digest → knowledge-memory autowrite path.

We assert on the candidate list `_collect_candidates` produces and the
resulting `MemoryValue` shapes, since that's the contract the memory
store sees. The store's actual `put` is exercised by the integration
tests in tests/integration/ai/memory/.
"""

from __future__ import annotations

from uuid import uuid4

from pathfinder.ai.graph.state import (
    PhaseDisposition,
    PipelineState,
    VerificationDigest,
)
from pathfinder.ai.memory.autowrite import _collect_candidates
from pathfinder.ai.memory.schemas import MemoryEntryDraft


def _state(*, digest: VerificationDigest | None) -> PipelineState:
    return PipelineState(
        conversation_id=uuid4(),
        user_id=uuid4(),
        site_id="plasmodb",
        mode="strategy",
        user_prompt="find Plasmodium kinases",
        verification_digest=digest,
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
    """A digest with empty `remember` adds nothing — verification doesn't
    have to author a memory every turn."""
    state = _state(digest=_digest(remember=[]))
    candidates = _collect_candidates(state)
    knowledge = [v for v, _key in candidates if v.kind == "knowledge"]
    assert knowledge == []


def test_no_digest_yields_no_knowledge_candidates() -> None:
    """If verification didn't run (or didn't return a digest), no knowledge
    autowrite — we never invent memories from non-verification phases."""
    state = _state(digest=None)
    candidates = _collect_candidates(state)
    knowledge = [v for v, _key in candidates if v.kind == "knowledge"]
    assert knowledge == []


def test_remember_lifts_to_full_memory_value() -> None:
    """A draft MemoryEntryDraft becomes a full MemoryValue with the
    site_id and source_conversation_id pulled from pipeline state — the
    LLM never authors those (no cross-chat leakage, no spoofed source)."""
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
    candidates = _collect_candidates(state)
    knowledge = [v for v, _key in candidates if v.kind == "knowledge"]
    assert len(knowledge) == 1
    mv = knowledge[0]

    assert mv.kind == "knowledge"
    assert mv.name == "P. falciparum kinome size"
    assert mv.summary.startswith("P. falciparum 3D7 has ~142")
    assert mv.content["count"] == 142
    assert mv.content["go_term"] == "GO:0016301"

    # Site id and source conversation id come from state, not the draft.
    assert mv.site_id == "plasmodb"
    assert mv.source_conversation_id == state.conversation_id

    # The draft's tags are preserved AND site_id is auto-appended once
    # so retrieval can scope by site without the LLM remembering to do so.
    assert "kinome" in mv.tags
    assert "kinase" in mv.tags
    assert "plasmodb" in mv.tags


def test_existing_site_tag_not_duplicated() -> None:
    """If the LLM redundantly tagged the site, autowrite must not duplicate
    — keeps tag lists tidy for retrieval."""
    draft = MemoryEntryDraft(
        name="x",
        summary="y",
        content={"k": "v"},
        tags=["plasmodb", "extra"],
    )
    state = _state(digest=_digest(remember=[draft]))
    candidates = _collect_candidates(state)
    mv = next(v for v, _ in candidates if v.kind == "knowledge")
    assert mv.tags.count("plasmodb") == 1
    assert "extra" in mv.tags


def test_multiple_drafts_get_distinct_keys() -> None:
    """Each draft gets its own deterministic key so re-running the same
    verification updates rather than duplicates, and different drafts in
    the same turn don't collide."""
    drafts = [
        MemoryEntryDraft(
            name=f"finding {i}",
            summary=f"summary {i}",
            content={"i": i},
        )
        for i in range(3)
    ]
    state = _state(digest=_digest(remember=drafts))
    candidates = _collect_candidates(state)
    knowledge_keys = [k for v, k in candidates if v.kind == "knowledge"]
    assert len(knowledge_keys) == 3
    assert len(set(knowledge_keys)) == 3
    for idx, key in enumerate(knowledge_keys):
        assert key == f"knowledge:{state.conversation_id.hex}:{idx}"


def test_verification_digest_carries_typed_routing_signal() -> None:
    """VerificationDigest carries the disposition + prose + reason routing
    fields; autowrite + the Lead's flow control depend on them."""
    digest = _digest(remember=[])
    assert digest.disposition == PhaseDisposition.DONE
    assert isinstance(digest.prose, str)
    assert isinstance(digest.reason, str)
    assert digest.success is True
    assert "142 hits" in digest.key_findings
