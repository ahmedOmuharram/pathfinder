"""The shape of an embedding call, so callers can inject one.

Defined next to the embedding integration rather than beside any one consumer:
it was previously declared twice, in `param_intent` and in
`public_strategy_search`, and a shared callable shape with two definitions is a
seam waiting to drift.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

EmbedFn = Callable[[Sequence[str]], Awaitable[list[list[float]]]]
