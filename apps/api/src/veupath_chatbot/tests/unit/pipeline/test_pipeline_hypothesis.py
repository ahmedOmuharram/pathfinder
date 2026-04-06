"""Property-based fuzzing of the AgentPipeline state machine.

Uses Hypothesis RuleBasedStateMachine to send random event sequences
and asserts the pipeline never enters an invalid state.
"""

from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from veupath_chatbot.ai.orchestration.pipeline import AgentPipeline, create_pipeline

VALID_PHASES = frozenset({"discovery", "planning", "execution", "verification", "completed", "failed"})

ALL_EVENTS = (
    "analyze",
    "finish_discovery",
    "submit_draft",
    "approve",
    "request_revision",
    "resubmit",
    "retry",
    "resume",
    "finish_execution",
    "present",
    "finish_verification",
    "replan",
    "retry_discovery",
    "abort_discovery",
    "abort_planning",
    "abort_execution",
    "abort_verification",
)


class PipelineStateMachine(RuleBasedStateMachine):
    """Fuzz the AgentPipeline with random event sequences."""

    def __init__(self) -> None:
        super().__init__()
        self.pipeline: AgentPipeline = create_pipeline()

    # ------------------------------------------------------------------
    # Invariants — checked after every rule
    # ------------------------------------------------------------------

    @invariant()
    def phase_is_valid(self) -> None:
        assert self.pipeline.current_phase in VALID_PHASES

    @invariant()
    def is_done_consistent_with_phase(self) -> None:
        phase = self.pipeline.current_phase
        if phase in ("completed", "failed"):
            assert self.pipeline.is_done is True
        else:
            assert self.pipeline.is_done is False

    @invariant()
    def transition_count_non_negative(self) -> None:
        assert self.pipeline._transition_count >= 0

    @invariant()
    def retry_counts_non_negative(self) -> None:
        for count in self.pipeline.retry_counts.values():
            assert count >= 0

    @invariant()
    def terminal_state_is_absorbing(self) -> None:
        """Once done, no event should change the phase."""
        if not self.pipeline.is_done:
            return
        frozen_phase = self.pipeline.current_phase
        frozen_count = self.pipeline._transition_count
        for event in ALL_EVENTS:
            self.pipeline.send(event)
        assert self.pipeline.current_phase == frozen_phase
        assert self.pipeline._transition_count == frozen_count

    # ------------------------------------------------------------------
    # Discovery phase rules (with preconditions)
    # ------------------------------------------------------------------

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "discovery")
    def analyze(self) -> None:
        self.pipeline.send("analyze")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "discovery")
    def finish_discovery(self) -> None:
        self.pipeline.send("finish_discovery")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "discovery")
    def abort_discovery(self) -> None:
        self.pipeline.send("abort_discovery")

    # ------------------------------------------------------------------
    # Planning phase rules (with preconditions)
    # ------------------------------------------------------------------

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "planning")
    def submit_draft(self) -> None:
        self.pipeline.send("submit_draft")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "planning")
    def approve(self) -> None:
        self.pipeline.send("approve")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "planning")
    def request_revision(self) -> None:
        self.pipeline.send("request_revision")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "planning")
    def resubmit(self) -> None:
        self.pipeline.send("resubmit")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "planning")
    def abort_planning(self) -> None:
        self.pipeline.send("abort_planning")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "planning")
    def retry_discovery(self) -> None:
        self.pipeline.send("retry_discovery")

    # ------------------------------------------------------------------
    # Execution phase rules (with preconditions)
    # ------------------------------------------------------------------

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "execution")
    def retry_exec(self) -> None:
        self.pipeline.send("retry")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "execution")
    def resume(self) -> None:
        self.pipeline.send("resume")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "execution")
    def finish_execution(self) -> None:
        self.pipeline.send("finish_execution")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "execution")
    def replan(self) -> None:
        self.pipeline.send("replan")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "execution")
    def abort_execution(self) -> None:
        self.pipeline.send("abort_execution")

    # ------------------------------------------------------------------
    # Verification phase rules (with preconditions)
    # ------------------------------------------------------------------

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "verification")
    def present(self) -> None:
        self.pipeline.send("present")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "verification")
    def finish_verification(self) -> None:
        self.pipeline.send("finish_verification")

    @rule()
    @precondition(lambda self: self.pipeline.current_phase == "verification")
    def abort_verification(self) -> None:
        self.pipeline.send("abort_verification")

    # ------------------------------------------------------------------
    # Untargeted rules — fire regardless of phase to test silent ignore.
    # No precondition: these must remain available even in terminal
    # states so Hypothesis always has at least one valid rule.
    # ------------------------------------------------------------------

    @rule()
    def fire_analyze_anywhere(self) -> None:
        self.pipeline.send("analyze")

    @rule()
    def fire_approve_anywhere(self) -> None:
        self.pipeline.send("approve")

    @rule()
    def fire_retry_anywhere(self) -> None:
        self.pipeline.send("retry")

    @rule()
    def fire_finish_verification_anywhere(self) -> None:
        self.pipeline.send("finish_verification")

    @rule()
    def fire_replan_anywhere(self) -> None:
        self.pipeline.send("replan")

    @rule()
    def fire_resubmit_anywhere(self) -> None:
        self.pipeline.send("resubmit")


TestPipelineFuzzing = PipelineStateMachine.TestCase
