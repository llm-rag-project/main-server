from __future__ import annotations

from app.core.errors import ErrorCode, build_error
from app.repositories.chat_repository import ChatRepository
from app.services.dify_service import DifyService
from app.schemas.chats import (
    ChatDetailResponse,
    ChatListItem,
    ChatListQuery,
    ChatListResponse,
    ChatSendMessageRequest,
    ChatSendMessageResponse,
    PageInfo,
)


class ChatService:
    def __init__(
        self,
        repository: ChatRepository,
        dify_service: DifyService | None = None,
    ):
        self.repository = repository
        self.dify_service = dify_service or DifyService()

    async def get_chat_list(
        self,
        user_id: int,
        query: ChatListQuery,
    ) -> ChatListResponse:
        rows, total = await self.repository.get_chat_list(
            user_id=user_id,
            query=query,
        )

        items = [ChatListItem(**row) for row in rows]
        has_next = query.page * query.size < total

        return ChatListResponse(
            items=items,
            page_info=PageInfo(
                page=query.page,
                size=query.size,
                total=total,
                has_next=has_next,
            ),
        )

    async def get_chat_detail(
        self,
        user_id: int,
        conversation_id: int,
    ) -> ChatDetailResponse:
        chat = await self.repository.get_chat_by_id(conversation_id)

        if not chat:
            raise build_error(ErrorCode.NOT_FOUND, "chat not found")

        if chat.user_id != user_id:
            raise build_error(
                ErrorCode.FORBIDDEN,
                "You do not have permission to access this chat",
            )

        return ChatDetailResponse(
            id=chat.id,
            title=chat.title,
            context_type=chat.context_type,
            external_conversation_id=chat.external_conversation_id,
            last_message=chat.last_message,
            last_message_at=chat.last_message_at,
            created_at=chat.created_at,
        )

    async def send_message(
        self,
        user_id: int,
        conversation_id: int,
        payload: ChatSendMessageRequest,
    ) -> ChatSendMessageResponse:
        chat = await self.repository.get_chat_by_id(conversation_id)

        if not chat:
            raise build_error(ErrorCode.NOT_FOUND, "chat not found")

        if chat.user_id != user_id:
            raise build_error(
                ErrorCode.FORBIDDEN,
                "You do not have permission to access this chat",
            )

        # 기사 목록이 있으면 Dify inputs로 전달
        inputs = {
            "conversation_id": chat.id,
            "context_type": chat.context_type,
            "article_ids": payload.article_ids or [],
        }

        try:
            dify_result = await self.dify_service.send_chat_message(
                query=payload.message,
                user=str(user_id),
                conversation_id=chat.external_conversation_id,
                inputs=inputs,
            )
        except RuntimeError:
            raise build_error(
                ErrorCode.UPSTREAM_ERROR,
                "LLM service temporarily unavailable",
            )

        conversation_id = dify_result.get("conversation_id")
        answer = dify_result.get("answer")
        created_at = dify_result.get("created_at")

        if not answer:
            raise build_error(
                ErrorCode.UPSTREAM_ERROR,
                "LLM service temporarily unavailable",
            )

        await self.repository.update_chat_conversation_and_last_message(
            chat=chat,
            external_conversation_id=conversation_id,
            last_message=answer,
            last_message_at=created_at,
        )

        return ChatSendMessageResponse(
            answer=answer,
            conversation_id=conversation_id,
            created_at=created_at,
        )