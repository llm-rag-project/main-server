from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.schemas.chats import ChatListQuery


class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_chat(
        self,
        user_id: int,
        title: str | None,
    ) -> dict[str, Any]:
        chat = Chat(
            user_id=user_id,
            title=title,
        )
        self.db.add(chat)
        await self.db.flush()
        await self.db.refresh(chat)

        return {
            "id": chat.id,
            "title": chat.title,
            "created_at": chat.created_at,
        }

    async def get_chat_by_id(self, conversation_id: int) -> Chat | None:
        stmt = select(Chat).where(Chat.id == conversation_id).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_chat_list(
        self,
        user_id: int,
        query: ChatListQuery,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = (
            select(
                Chat.id,
                Chat.title,
                Chat.last_message,
                Chat.last_message_at,
                Chat.created_at,
            )
            .where(Chat.user_id == user_id)
        )

        if query.q:
            stmt = stmt.where(Chat.title.ilike(f"%{query.q.strip()}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt)
        total = total or 0

        stmt = (
            stmt.order_by(Chat.created_at.desc(), Chat.id.desc())
            .offset((query.page - 1) * query.size)
            .limit(query.size)
        )

        result = await self.db.execute(stmt)
        rows = result.mappings().all()

        return [dict(row) for row in rows], total

    async def update_chat_conversation_and_last_message(
        self,
        chat: Chat,
        external_conversation_id: str | None,
        last_message: str | None,
        last_message_at: datetime | None,
    ) -> None:
        if external_conversation_id and not chat.external_conversation_id:
            chat.external_conversation_id = external_conversation_id

        chat.last_message = last_message
        chat.last_message_at = last_message_at
        await self.db.flush()

    async def delete_chat(self, chat: Chat) -> None:
        await self.db.delete(chat)
        await self.db.flush()