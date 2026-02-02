"""Shared router helpers for resource lookup and authorization."""

from uuid import UUID

from veupath_chatbot.platform.errors import ErrorCode, ForbiddenError, NotFoundError
from veupath_chatbot.persistence.models import Strategy
from veupath_chatbot.persistence.repo import StrategyRepository


async def get_strategy_or_404(
    strategy_repo: StrategyRepository, strategy_id: UUID
) -> Strategy:
    strategy = await strategy_repo.get_by_id(strategy_id)
    if not strategy:
        raise NotFoundError(code=ErrorCode.STRATEGY_NOT_FOUND, title="Strategy not found")
    return strategy


def require_strategy_owner(strategy: Strategy, user_id: UUID) -> None:
    if strategy.user_id != user_id:
        raise ForbiddenError()


async def get_owned_strategy_or_404(
    strategy_repo: StrategyRepository, strategy_id: UUID, user_id: UUID
) -> Strategy:
    strategy = await get_strategy_or_404(strategy_repo, strategy_id)
    require_strategy_owner(strategy, user_id)
    return strategy

