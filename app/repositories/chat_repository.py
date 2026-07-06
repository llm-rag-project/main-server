from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.models.chat_message import ChatMessage
from app.schemas.chats import ChatListQuery


class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_chat(
        self,
        user_id: int,
        title: str | None,
        keyword_id: int | None = None,
    ) -> dict[str, Any]:
        chat = Chat(
            user_id=user_id,
            keyword_id=keyword_id,
            title=title,
        )
        self.db.add(chat)
        await self.db.flush()
        await self.db.refresh(chat)

        return {
            "id": chat.id,
            "keyword_id": chat.keyword_id,
            "title": chat.title,
            "created_at": chat.created_at,
        }

    async def get_chat_by_id(self, conversation_id: int) -> Chat | None:
        stmt = select(Chat).where(Chat.id == conversation_id).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_chat_by_keyword(self, *, user_id: int, keyword_id: int) -> Chat | None:
        result = await self.db.execute(
            select(Chat)
            .where(Chat.user_id == user_id, Chat.keyword_id == keyword_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_chat_list(
        self,
        user_id: int,
        query: ChatListQuery,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = (
            select(
                Chat.id,
                Chat.keyword_id,
                Chat.title,
                Chat.last_message,
                Chat.last_message_at,
                Chat.created_at,
            )
            .where(Chat.user_id == user_id)
        )

        if query.q:
            stmt = stmt.where(Chat.title.ilike(f"%{query.q.strip()}%"))

        if query.keyword_id:
            stmt = stmt.where(Chat.keyword_id == query.keyword_id)

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

    async def reset_chat(self, chat: Chat) -> None:
        await self.db.execute(delete(ChatMessage).where(ChatMessage.chat_id == chat.id))
        chat.external_conversation_id = None
        chat.last_message = None
        chat.last_message_at = None
        await self.db.flush()

    async def add_message(
        self,
        *,
        chat_id: int,
        user_id: int,
        role: str,
        content: str,
        external_conversation_id: str | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            chat_id=chat_id,
            user_id=user_id,
            role=role,
            content=content,
            external_conversation_id=external_conversation_id,
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def get_messages(self, *, chat_id: int, user_id: int, limit: int = 200) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id, ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_chat(self, chat: Chat) -> None:
        await self.db.delete(chat)
        await self.db.flush()
