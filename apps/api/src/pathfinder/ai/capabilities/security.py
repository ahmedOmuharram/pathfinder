"""Security guardrail capability — PIGuard + invisible-text scanning.

Runs PIGuard (ONNX) prompt-injection detection and invisible-text
scanning on every model request.  No output scanning — PathFinder's
domain (gene searches, strategy building) doesn't require toxicity,
PII, or refusal detection.

The ONNX model and tokenizer are lazy-initialized on first use so
the filesystem hit happens only once per process lifetime.
Initialization runs in a thread executor to avoid blocking the async
event loop.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic_ai.capabilities.abstract import AbstractCapability
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import RunContext

from pathfinder.ai.capabilities.piguard import (
    InvisibleTextScanner,
    PIGuardScanner,
    SecurityRejectionError,
    resolve_model_dir,
)
from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_user_text(messages: Sequence[object]) -> str:
    """Extract the latest user text from a message list.

    Walks the message list in reverse to find the most recent
    ``ModelRequest`` containing a ``UserPromptPart`` with string content.
    Returns the empty string if none is found.
    """
    for message in reversed(messages):
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                return part.content
    return ""


# ---------------------------------------------------------------------------
# SecurityGuardrail capability
# ---------------------------------------------------------------------------

# Scanner protocol — both PIGuardScanner and InvisibleTextScanner satisfy it.
_Scanner = PIGuardScanner | InvisibleTextScanner


@dataclass
class SecurityGuardrail(AbstractCapability[AgentDeps]):
    """Scans LLM inputs using PIGuard and invisible-text detection.

    Input scanners reject prompts that trigger prompt-injection or
    invisible-text detectors.  No output scanning is performed —
    PathFinder's domain (gene searches, strategy building) doesn't
    require toxicity, PII, or refusal detection.

    Scanners are lazy-initialized on first use so the filesystem hit
    happens only once per process.  Initialization is thread-safe
    and runs in a thread executor to avoid blocking the event loop.
    """

    injection_threshold: float = 0.70
    model_dir: Path = field(default_factory=resolve_model_dir)

    _scanners: list[_Scanner] = field(
        default_factory=list, init=False, repr=False
    )
    _initialized: bool = field(default=False, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # -----------------------------------------------------------------------
    # Lazy initialization (thread-safe, non-blocking)
    # -----------------------------------------------------------------------

    def _init_scanners_sync(self) -> None:
        """Build scanners synchronously. Called from a thread executor."""
        with self._lock:
            if self._initialized:
                return

            self._scanners = [
                PIGuardScanner(
                    model_dir=self.model_dir,
                    threshold=self.injection_threshold,
                ),
                InvisibleTextScanner(),
            ]

            self._initialized = True
            logger.info("Security guardrail initialized (PIGuard + InvisibleText)")

    async def _ensure_initialized(self) -> None:
        """Initialize scanners if needed, without blocking the event loop."""
        if self._initialized:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._init_scanners_sync)

    # -----------------------------------------------------------------------
    # Input scanning (before model request)
    # -----------------------------------------------------------------------

    async def before_model_request(
        self,
        ctx: RunContext[AgentDeps],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        """Scan the latest user text before sending to the model.

        Raises ``SecurityRejectionError`` if any input scanner rejects.
        """
        await self._ensure_initialized()

        user_text = _extract_user_text(request_context.messages)
        if not user_text:
            return request_context

        for scanner in self._scanners:
            scanner_name = type(scanner).__name__
            _sanitized, is_valid, risk_score = scanner.scan(user_text)
            if not is_valid:
                logger.warning(
                    "Input rejected by security scanner",
                    scanner=scanner_name,
                    risk_score=risk_score,
                )
                raise SecurityRejectionError(scanner_name, risk_score)
            logger.debug(
                "Input scanner passed",
                scanner=scanner_name,
                risk_score=risk_score,
            )

        return request_context
