"""Tests for _extract_cached_tokens — provider-agnostic cached token extraction."""

from dataclasses import dataclass, field

from veupath_chatbot.services.chat.streaming import _extract_cached_tokens


class _DottableDict(dict):
    """Mirrors Kani's DottableDict: __getattr__ delegates to __getitem__."""

    def __getattr__(self, item: str) -> object:
        return self[item]


@dataclass
class FakeMsg:
    """Minimal stand-in for a kani ChatMessage with an optional extra dict."""

    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class FakeUsage:
    """Minimal Anthropic usage object."""

    cache_read_input_tokens: int | None = None
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class FakeAnthropicMsg:
    """Minimal Anthropic message with a usage object."""

    usage: FakeUsage = field(default_factory=FakeUsage)


@dataclass
class FakeGoogleMetadata:
    """Minimal Google usage metadata."""

    cached_content_token_count: int | None = None


@dataclass
class FakeGoogleResponse:
    """Minimal Google response with usage metadata."""

    usage_metadata: FakeGoogleMetadata = field(default_factory=FakeGoogleMetadata)


def test_returns_0_for_msg_without_extra():
    msg = object()  # no extra attribute
    assert _extract_cached_tokens(msg) == 0


def test_returns_0_for_empty_extra():
    msg = FakeMsg(extra={})
    assert _extract_cached_tokens(msg) == 0


# ── OpenAI Chat Completions ─────────────────────────────────────────
def test_openai_chat_completions_with_cached_tokens():
    """Chat Completions usage has prompt_tokens_details.cached_tokens."""
    msg = FakeMsg(
        extra={
            "openai_usage": _DottableDict(
                {
                    "prompt_tokens": 10000,
                    "completion_tokens": 500,
                    "prompt_tokens_details": {"cached_tokens": 7500},
                }
            )
        }
    )
    assert _extract_cached_tokens(msg) == 7500


def test_openai_chat_completions_without_details():
    """Chat Completions usage missing prompt_tokens_details entirely."""
    msg = FakeMsg(
        extra={
            "openai_usage": _DottableDict(
                {
                    "prompt_tokens": 10000,
                    "completion_tokens": 500,
                }
            )
        }
    )
    assert _extract_cached_tokens(msg) == 0


def test_openai_chat_completions_cached_tokens_zero():
    """prompt_tokens_details exists but cached_tokens is 0."""
    msg = FakeMsg(
        extra={
            "openai_usage": _DottableDict(
                {
                    "prompt_tokens": 10000,
                    "prompt_tokens_details": {"cached_tokens": 0},
                }
            )
        }
    )
    assert _extract_cached_tokens(msg) == 0


# ── OpenAI Responses API ────────────────────────────────────────────
def test_openai_responses_api_with_cached_tokens():
    """Responses API uses input_tokens_details.cached_tokens."""
    msg = FakeMsg(
        extra={
            "openai_usage": _DottableDict(
                {
                    "input_tokens": 10000,
                    "output_tokens": 500,
                    "input_tokens_details": {"cached_tokens": 8000},
                }
            )
        }
    )
    assert _extract_cached_tokens(msg) == 8000


# ── Anthropic ────────────────────────────────────────────────────────
def test_anthropic_cache_read_tokens():
    """Anthropic message.usage.cache_read_input_tokens."""
    msg = FakeMsg(
        extra={
            "anthropic_message": FakeAnthropicMsg(
                usage=FakeUsage(cache_read_input_tokens=5000)
            )
        }
    )
    assert _extract_cached_tokens(msg) == 5000


def test_anthropic_no_cache_field():
    """Anthropic message without cache_read_input_tokens."""
    msg = FakeMsg(
        extra={
            "anthropic_message": FakeAnthropicMsg(
                usage=FakeUsage(cache_read_input_tokens=None)
            )
        }
    )
    assert _extract_cached_tokens(msg) == 0


# ── Google Gemini ────────────────────────────────────────────────────
def test_google_cached_content_token_count():
    """Google response.usage_metadata.cached_content_token_count."""
    msg = FakeMsg(
        extra={
            "google_response": FakeGoogleResponse(
                usage_metadata=FakeGoogleMetadata(cached_content_token_count=3000)
            )
        }
    )
    assert _extract_cached_tokens(msg) == 3000


# ── Priority: OpenAI > Anthropic > Google ────────────────────────────
def test_prefers_openai_over_anthropic():
    """If both openai_usage and anthropic_message exist, openai wins."""
    msg = FakeMsg(
        extra={
            "openai_usage": _DottableDict(
                {"prompt_tokens_details": {"cached_tokens": 5000}}
            ),
            "anthropic_message": FakeAnthropicMsg(
                usage=FakeUsage(cache_read_input_tokens=1000)
            ),
        }
    )
    assert _extract_cached_tokens(msg) == 5000
