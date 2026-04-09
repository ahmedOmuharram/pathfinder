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
import os
import threading
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import onnxruntime
from pydantic_ai.capabilities.abstract import AbstractCapability
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import RunContext
from tokenizers import Tokenizer

from pathfinder.ai.orchestration.deps import AgentDeps
from pathfinder.platform.errors import AppError, ErrorCode
from pathfinder.platform.logging import get_logger

logger = get_logger(__name__)

# Default model directory — baked into the Docker image at build time.
# Override via PIGUARD_MODEL_DIR env var for local dev/test.
_DOCKER_MODEL_DIR = "/app/models/piguard"


def _resolve_model_dir() -> Path:
    """Resolve PIGuard model directory, checking PIGUARD_MODEL_DIR env var."""
    return Path(os.environ.get("PIGUARD_MODEL_DIR", _DOCKER_MODEL_DIR))


# ---------------------------------------------------------------------------
# Domain error
# ---------------------------------------------------------------------------


class SecurityRejectionError(AppError):
    """Raised when a security scanner rejects user input."""

    def __init__(self, scanner: str, risk_score: float) -> None:
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            title="Input rejected by security screening",
            status=403,
            detail="Your message was flagged by our safety system. Please rephrase and try again.",
        )
        self.scanner = scanner
        self.risk_score = risk_score


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
# PIGuard ONNX scanner
# ---------------------------------------------------------------------------

# Unicode categories that indicate invisible / control characters.
_INVISIBLE_CATEGORIES = frozenset({"Cf", "Co", "Cn"})


class PIGuardScanner:
    """Prompt-injection detection via PIGuard ONNX model.

    Loads the ONNX session and fast tokenizer from *model_dir*.
    Inference is pure NumPy — no PyTorch, no transformers at runtime.
    """

    def __init__(self, model_dir: Path, threshold: float = 0.70) -> None:
        model_path = model_dir / "model.onnx"
        tokenizer_path = model_dir / "tokenizer.json"

        self._session = onnxruntime.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._tokenizer.enable_truncation(max_length=512)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=512)
        self._threshold = threshold

    def scan(self, text: str) -> tuple[str, bool, float]:
        """Classify *text* as benign or injection.

        Returns ``(text, is_valid, injection_score)`` matching the
        scanner interface used by ``SecurityGuardrail``.
        """
        encoded = self._tokenizer.encode(text)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

        raw_output = self._session.run(
            None,
            {"input_ids": input_ids, "attention_mask": attention_mask},
        )
        logits = np.asarray(raw_output[0])

        # Row-wise softmax → injection probability.
        shifted = logits - logits.max(axis=1, keepdims=True)
        exp = np.exp(shifted)
        probs = exp / exp.sum(axis=1, keepdims=True)
        injection_score = round(float(probs[0][1]), 4)
        is_valid = injection_score < self._threshold
        return text, is_valid, injection_score


# ---------------------------------------------------------------------------
# Invisible-text scanner (pure Python, no ML)
# ---------------------------------------------------------------------------


class InvisibleTextScanner:
    """Detect and strip invisible Unicode characters.

    Flags characters in Unicode categories Cf (format), Co (private use),
    and Cn (unassigned).  Returns the cleaned text and ``is_valid=False``
    when invisible characters are found.
    """

    def scan(self, text: str) -> tuple[str, bool, float]:
        # Fast path: pure-ASCII text has no invisible chars.
        if text.isascii():
            return text, True, 0.0

        has_invisible = any(
            unicodedata.category(ch) in _INVISIBLE_CATEGORIES for ch in text
        )
        if not has_invisible:
            return text, True, 0.0

        cleaned = "".join(
            ch for ch in text if unicodedata.category(ch) not in _INVISIBLE_CATEGORIES
        )
        return cleaned, False, 1.0


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
    model_dir: Path = field(default_factory=_resolve_model_dir)

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
