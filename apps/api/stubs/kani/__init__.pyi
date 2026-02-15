"""Stub package for kani - re-exports for type checking.

The kani package does not ship with inline types. This stub re-exports
commonly used symbols so imports like `from kani import Kani` type-check.
"""

from kani.ai_function import AIParam, ai_function
from kani.kani import Kani
from kani.models import ChatMessage, ChatRole

__all__ = ["AIParam", "ChatMessage", "ChatRole", "Kani", "ai_function"]
