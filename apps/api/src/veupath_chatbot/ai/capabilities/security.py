"""Security guardrail capability — LLM Guard input/output scanning.

Runs LLM Guard scanners on every model request/response to detect prompt
injection, invisible text, toxicity, secrets (input) and sensitive PII,
toxicity, and refusal patterns (output).

Scanners are lazy-initialized on first use so model downloads only happen
once per process lifetime.  Initialization runs in a thread executor to
avoid blocking the async event loop.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.capabilities.abstract import AbstractCapability
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import RunContext

from veupath_chatbot.ai.orchestration.deps import AgentDeps
from veupath_chatbot.platform.errors import AppError, ErrorCode
from veupath_chatbot.platform.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Type aliases for scanner protocols
# ---------------------------------------------------------------------------

# LLM Guard scanners are lazy-imported; use Any to avoid eager model loads.
_InputScanner = Any
_OutputScanner = Any


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


def _extract_user_text(messages: list[Any]) -> str:
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


def _build_input_scanners(
    *,
    injection_threshold: float,
    toxicity_threshold: float,
    use_onnx: bool,
) -> list[_InputScanner]:
    """Construct input scanners. Separated for lazy-init."""
    import llm_guard.input_scanners
    return [
        llm_guard.input_scanners.PromptInjection(
            threshold=injection_threshold,
            use_onnx=use_onnx,
        ),
        llm_guard.input_scanners.InvisibleText(),
        llm_guard.input_scanners.Toxicity(
            threshold=toxicity_threshold,
            use_onnx=use_onnx,
        ),
        llm_guard.input_scanners.Secrets(),  # regex-based, no ML model
    ]


def _build_output_scanners(
    *,
    toxicity_threshold: float,
    use_onnx: bool,
) -> list[_OutputScanner]:
    """Construct output scanners. Separated for lazy-init."""
    import llm_guard.output_scanners
    return [
        llm_guard.output_scanners.Sensitive(redact=True, use_onnx=use_onnx),
        llm_guard.output_scanners.Toxicity(
            threshold=toxicity_threshold,
            use_onnx=use_onnx,
        ),
        llm_guard.output_scanners.NoRefusal(use_onnx=use_onnx),
    ]


# ---------------------------------------------------------------------------
# SecurityGuardrail capability
# ---------------------------------------------------------------------------


@dataclass
class SecurityGuardrail(AbstractCapability[AgentDeps]):
    """Scans LLM inputs and outputs using LLM Guard.

    Input scanners reject prompts that trigger injection, invisible text,
    toxicity, or secrets detectors. Output scanners redact PII in-place and
    log refusal warnings.

    All scanners are lazy-initialized on first use so that heavy model
    downloads happen only once per process.  Initialization is thread-safe
    and runs in a thread executor to avoid blocking the event loop.
    """

    injection_threshold: float = 0.92
    toxicity_threshold: float = 0.7
    use_onnx: bool = True

    _input_scanners: list[_InputScanner] = field(
        default_factory=list, init=False, repr=False
    )
    _output_scanners: list[_OutputScanner] = field(
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

            self._input_scanners = _build_input_scanners(
                injection_threshold=self.injection_threshold,
                toxicity_threshold=self.toxicity_threshold,
                use_onnx=self.use_onnx,
            )

            self._output_scanners = _build_output_scanners(
                toxicity_threshold=self.toxicity_threshold,
                use_onnx=self.use_onnx,
            )

            self._initialized = True
            logger.info("Security guardrail initialized")

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

        for scanner in self._input_scanners:
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

    # -----------------------------------------------------------------------
    # Output scanning (after model response)
    # -----------------------------------------------------------------------

    async def after_model_request(
        self,
        ctx: RunContext[AgentDeps],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        """Scan model output. Redacts PII in-place, logs refusal warnings."""
        await self._ensure_initialized()

        user_text = _extract_user_text(request_context.messages)

        for part in response.parts:
            if not isinstance(part, TextPart):
                continue

            for scanner in self._output_scanners:
                scanner_name = type(scanner).__name__
                sanitized, is_valid, risk_score = scanner.scan(
                    user_text, part.content
                )
                if not is_valid:
                    if scanner_name == "NoRefusal":
                        # Log-only for refusal detection — do not block.
                        logger.warning(
                            "Model refusal detected",
                            scanner=scanner_name,
                            risk_score=risk_score,
                        )
                    else:
                        logger.warning(
                            "Output sanitized by security scanner",
                            scanner=scanner_name,
                            risk_score=risk_score,
                        )
                        part.content = sanitized

        return response
