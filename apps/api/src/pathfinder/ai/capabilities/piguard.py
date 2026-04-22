"""PIGuard + invisible-text scanners — pure, no agent dependencies.

Kept separate from :mod:`pathfinder.ai.capabilities.security` so the
scanner construction + warm-up hook don't drag in the agent package
(which would trigger a circular import at startup).
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import numpy as np
import onnxruntime
from tokenizers import Tokenizer

from pathfinder.platform.errors import AppError, ErrorCode

# Default model directory — baked into the Docker image at build time.
# Override via PIGUARD_MODEL_DIR env var for local dev/test.
_DOCKER_MODEL_DIR = "/app/models/piguard"


def resolve_model_dir() -> Path:
    """Resolve PIGuard model directory, checking PIGUARD_MODEL_DIR env var."""
    return Path(os.environ.get("PIGUARD_MODEL_DIR", _DOCKER_MODEL_DIR))


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

        Returns ``(text, is_valid, injection_score)``.
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


def warm_up_piguard() -> None:
    """Prime the ONNX session + tokenizer at startup.

    The first request otherwise pays a 3-7s cold-load penalty when
    ``UserInputScanner`` lazy-initialises its scanners. Calling this at
    startup warms the OS page cache and the onnxruntime library.
    """
    PIGuardScanner(model_dir=resolve_model_dir())
