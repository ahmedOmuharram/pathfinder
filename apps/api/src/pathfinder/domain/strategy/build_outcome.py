from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StepPushFailure:
    step_id: str
    search_name: str
    error: str


@dataclass
class BuildOutcome:
    """Structured result of a declarative strategy build."""

    pushed_step_ids: list[str] = field(default_factory=list)
    failed_steps: list[StepPushFailure] = field(default_factory=list)
    skipped_step_ids: list[str] = field(default_factory=list)
    wdk_strategy_id: int | None = None
    wdk_url: str | None = None
    counts: dict[str, int | None] = field(default_factory=dict)
    root_count: int | None = None
    zero_step_ids: list[str] = field(default_factory=list)

    @property
    def fully_succeeded(self) -> bool:
        return not self.failed_steps and not self.skipped_step_ids
