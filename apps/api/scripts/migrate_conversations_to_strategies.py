"""One-time migration: merge conversations into strategies.

Usage:
  uv run python scripts/migrate_conversations_to_strategies.py

This copies conversations.messages/thinking/title into strategies and drops
the conversations table. Run once after deploying the unified Strategy model.
"""

import asyncio
import json

from sqlalchemy import text
from sqlalchemy.engine import make_url

from veupath_chatbot.core.config import get_settings
from veupath_chatbot.db.session import get_db_context


async def _ensure_strategy_columns(session, is_sqlite: bool) -> None:
    if is_sqlite:
        result = await session.execute(text("PRAGMA table_info(strategies)"))
        columns = {row[1] for row in result.fetchall()}
        if "title" not in columns:
            await session.execute(
                text("ALTER TABLE strategies ADD COLUMN title VARCHAR(255)")
            )
        if "messages" not in columns:
            await session.execute(
                text("ALTER TABLE strategies ADD COLUMN messages JSON")
            )
        if "thinking" not in columns:
            await session.execute(
                text("ALTER TABLE strategies ADD COLUMN thinking JSON")
            )
    else:
        await session.execute(
            text("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS title VARCHAR(255)")
        )
        await session.execute(
            text("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS messages JSON")
        )
        await session.execute(
            text("ALTER TABLE strategies ADD COLUMN IF NOT EXISTS thinking JSON")
        )


async def main() -> None:
    settings = get_settings()
    db_url = make_url(settings.database_url)
    is_sqlite = db_url.drivername.startswith("sqlite")

    async with get_db_context() as session:
        if is_sqlite:
            exists = await session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
                )
            )
            has_table = exists.scalar() is not None
        else:
            exists = await session.execute(text("SELECT to_regclass('public.conversations')"))
            has_table = exists.scalar() is not None

        if not has_table:
            print("No conversations table found. Nothing to migrate.")
            return

        await _ensure_strategy_columns(session, is_sqlite)

        rows = await session.execute(
            text("SELECT id, title, messages, thinking FROM conversations")
        )
        updates = 0
        for row in rows.mappings():
            await session.execute(
                text(
                    """
                    UPDATE strategies
                    SET title = COALESCE(title, :title),
                        messages = COALESCE(messages, :messages),
                        thinking = COALESCE(thinking, :thinking)
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "title": row["title"],
                    "messages": row["messages"] if row["messages"] is not None else json.dumps([]),
                    "thinking": row["thinking"],
                },
            )
            updates += 1

        await session.execute(text("DROP TABLE conversations"))
        print(f"Migrated {updates} conversation rows into strategies.")


if __name__ == "__main__":
    asyncio.run(main())
