# EDA acceptance suite

Frozen, behavior-only conformance tests for the EDA integration plan
(`docs/knowledge/eda/plan/`), written before batch 1 from the pinned contract
and the bundle's live-verified values. Every assertion pins a value.

**No-edit rule.** Implementers may not modify anything in this tree; a verifier
fails the batch on any hunk here. A wrong test escalates to the session lead,
with evidence; only the lead edits this suite.

    cd apps/api
    uv run pytest -m eda_acceptance src/pathfinder/tests/acceptance/eda/ -v --override-ini addopts=''

Each module skips through `pytest.importorskip` until its code exists.
Fixtures are inline in each file by design, never an implementer's path.
