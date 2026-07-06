from __future__ import annotations

from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo

from app.core.errors import ErrorCode, build_error
from app.repositories.article_repository import ArticleRepository
from app.repositories.chat_repository import ChatRepository
from app.repositories.keyword_repository import get_keyword_by_id
from app.repositories.stats_repository import StatsRepository
from app.schemas.articles import ArticleListQuery, ArticleSort
from app.schemas.chats import (
    ChatDetailResponse,
    ChatListItem,
    ChatListQuery,
    ChatListResponse,
    ChatMessageItem,
    ChatSendMessageRequest,
    ChatSendMessageResponse,
    PageInfo,
)
from app.services.dify_service import DifyService
from app.services.stats_service import StatsService


KST = ZoneInfo("Asia/Seoul")


class ChatService:
    def __init__(
        self,
        repository: ChatRepository,
        dify_service: DifyService | None = None,
    ):
        self.repository = repository
        self.dify_service = dify_service or DifyService.from_settings()

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

    async def _validate_keyword_owner(self, *, user_id: int, keyword_id: int | None) -> None:
        if keyword_id is None:
            return
        keyword = await get_keyword_by_id(self.repository.db, keyword_id)
        if not keyword:
            raise build_error(ErrorCode.NOT_FOUND, "keyword not found")
        if keyword.user_id != user_id:
            raise build_error(ErrorCode.FORBIDDEN, "You do not have permission to access this keyword")

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

        messages = await self.repository.get_messages(chat_id=chat.id, user_id=user_id)
        message_items = [
            ChatMessageItem(
                id=message.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
            )
            for message in messages
        ]

        if not message_items and chat.last_message:
            message_items.append(
                ChatMessageItem(
                    id=0,
                    role="assistant",
                    content=chat.last_message,
                    created_at=chat.last_message_at or chat.created_at,
                )
            )

        return ChatDetailResponse(
            id=chat.id,
            keyword_id=chat.keyword_id,
            title=chat.title,
            external_conversation_id=chat.external_conversation_id,
            last_message=chat.last_message,
            last_message_at=chat.last_message_at,
            created_at=chat.created_at,
            messages=message_items,
        )

    async def send_message(
        self,
        user_id: int,
        chat_id: int,
        payload: ChatSendMessageRequest,
    ) -> ChatSendMessageResponse:
        chat = await self.repository.get_chat_by_id(chat_id)

        if not chat:
            raise build_error(ErrorCode.NOT_FOUND, "chat not found")

        if chat.user_id != user_id:
            raise build_error(
                ErrorCode.FORBIDDEN,
                "You do not have permission to access this chat",
            )

        article_id = None
        if payload.article_ids:
            article_id = payload.article_ids[0]

        await self.repository.add_message(
            chat_id=chat.id,
            user_id=user_id,
            role="user",
            content=payload.message,
            external_conversation_id=payload.conversation_id or chat.external_conversation_id,
        )

        briefing_context = await self._build_briefing_context(user_id=user_id, keyword_id=chat.keyword_id)

        dify_result = await self.dify_service.send_chat_message(
            user_id=user_id,
            message=payload.message,
            conversation_id=payload.conversation_id or chat.external_conversation_id or "",
            article_id=article_id,
            briefing_context=briefing_context,
        )

        new_conversation_id = dify_result.get("conversation_id")
        answer = dify_result.get("answer")
        created_at = datetime.now(timezone.utc)

        if not answer:
            raise build_error(
                ErrorCode.UPSTREAM_ERROR,
                f"LLM 응답에 answer가 없습니다. dify_result={dify_result}",
            )

        await self.repository.update_chat_conversation_and_last_message(
            chat=chat,
            external_conversation_id=new_conversation_id,
            last_message=answer,
            last_message_at=created_at,
        )

        assistant_message = await self.repository.add_message(
            chat_id=chat.id,
            user_id=user_id,
            role="assistant",
            content=answer,
            external_conversation_id=new_conversation_id,
        )

        return ChatSendMessageResponse(
            answer=answer,
            conversation_id=new_conversation_id,
            created_at=assistant_message.created_at,
        )

    async def _build_briefing_context(self, *, user_id: int, keyword_id: int | None) -> str:
        keyword = await get_keyword_by_id(self.repository.db, keyword_id) if keyword_id else None
        keyword_name = keyword.keyword_text if keyword else "전체 키워드"
        stats_service = StatsService(StatsRepository(self.repository.db))
        article_stats = await stats_service.get_article_stats(user_id=user_id, days=7)
        analysis_stats = await stats_service.get_analysis_stats(user_id=user_id, days=7)
        search_volume = await stats_service.get_keyword_search_volume(user_id=user_id)

        def _filter(rows: list[dict], key: str = "keyword_id") -> list[dict]:
            if not keyword_id:
                return rows
            return [row for row in rows if row.get(key) == keyword_id or row.get("keyword_text") == keyword_name]

        by_keyword = _filter(article_stats.get("by_keyword", []))
        by_collected_date = _filter(article_stats.get("by_keyword_collected_date", []))
        sentiment_rows = _filter(analysis_stats.get("sentiment_by_keyword", []), key="keyword_text")
        promotion_rows = _filter(analysis_stats.get("promotion_by_keyword", []), key="keyword_text")
        volume_rows = _filter(search_volume)
        volume_row = volume_rows[0] if volume_rows else {}

        article_count_7d = sum(int(row.get("article_count") or 0) for row in by_keyword)
        today = datetime.now(KST).strftime("%Y-%m-%d")
        today_collected = sum(
            int(row.get("article_count") or 0)
            for row in by_collected_date
            if row.get("date") == today
        )

        def _sentiment_count(label: str) -> int:
            total = 0
            for row in sentiment_rows:
                text = str(row.get("sentiment") or "").lower()
                if label == "positive" and ("긍정" in text or "positive" in text):
                    total += int(row.get("count") or 0)
                if label == "negative" and ("부정" in text or "negative" in text):
                    total += int(row.get("count") or 0)
                if label == "neutral" and ("중립" in text or "neutral" in text):
                    total += int(row.get("count") or 0)
            return total

        positive_count = _sentiment_count("positive")
        negative_count = _sentiment_count("negative")
        neutral_count = _sentiment_count("neutral")
        sentiment_total = positive_count + negative_count + neutral_count
        negative_rate = round((negative_count / sentiment_total) * 100) if sentiment_total else 0
        promotion_count = sum(
            int(row.get("count") or 0)
            for row in promotion_rows
            if row.get("is_promotion") is True or "광고" in str(row.get("promotion") or "")
        )
        promotion_total = sum(int(row.get("count") or 0) for row in promotion_rows)
        promotion_rate = round((promotion_count / promotion_total) * 100) if promotion_total else 0

        priority_query = ArticleListQuery(
            page=1,
            size=5,
            keyword_id=keyword_id,
            sort=ArticleSort.importance_desc,
        )
        priority_rows, _ = await ArticleRepository(self.repository.db).get_article_list(
            user_id=user_id,
            query=priority_query,
        )

        context = {
            "purpose": "AI 채팅 답변 시 사용자가 선택한 키워드의 뉴스/마케팅 브리핑 컨텍스트입니다. 사용자의 질문에 직접 답하되, 필요한 경우 이 지표를 근거로 활용하세요.",
            "keyword": {
                "id": keyword_id,
                "name": keyword_name,
            },
            "period": {
                "days": 7,
                "today": today,
            },
            "metrics": {
                "article_count_7d": article_count_7d,
                "today_collected_article_count": today_collected,
                "news_search_latest_count": volume_row.get("total_count", 0),
                "sns_mention_7d": volume_row.get("social_total_count", 0),
                "sns_negative_hint_count": volume_row.get("social_negative_hint_count", 0),
                "positive_article_count": positive_count,
                "neutral_article_count": neutral_count,
                "negative_article_count": negative_count,
                "negative_rate_percent": negative_rate,
                "promotion_rate_percent": promotion_rate,
            },
            "recent_collection_trend": by_collected_date[-7:],
            "priority_articles": [
                {
                    "title": row.get("title"),
                    "source": row.get("source"),
                    "published_at": row.get("published_at").isoformat() if row.get("published_at") else None,
                    "importance": row.get("importance"),
                    "summary": row.get("summary"),
                }
                for row in priority_rows
            ],
        }
        return json.dumps(context, ensure_ascii=False, default=str)

    async def create_chat(
        self,
        user_id: int,
        payload,
    ) -> ChatDetailResponse:
        title = (payload.title or "").strip()
        keyword_id = getattr(payload, "keyword_id", None)

        await self._validate_keyword_owner(user_id=user_id, keyword_id=keyword_id)

        if keyword_id is not None:
            existing = await self.repository.get_chat_by_keyword(user_id=user_id, keyword_id=keyword_id)
            if existing:
                return await self.get_chat_detail(user_id=user_id, conversation_id=existing.id)

        if not title:
            raise build_error(ErrorCode.VALIDATION_ERROR, "채팅방 제목은 비어 있을 수 없습니다.")

        chat = await self.repository.create_chat(
            user_id=user_id,
            title=title,
            keyword_id=keyword_id,
        )

        return ChatDetailResponse(
            id=chat["id"],
            keyword_id=chat.get("keyword_id"),
            title=chat["title"],
            external_conversation_id=chat.get("external_conversation_id"),
            last_message=chat.get("last_message"),
            last_message_at=chat.get("last_message_at"),
            created_at=chat["created_at"],
            messages=[],
        )

    async def delete_chat(
        self,
        user_id: int,
        chat_id: int,
    ) -> dict:
        chat = await self.repository.get_chat_by_id(chat_id)

        if not chat:
            raise build_error(ErrorCode.NOT_FOUND, "chat not found")

        if chat.user_id != user_id:
            raise build_error(
                ErrorCode.FORBIDDEN,
                "You do not have permission to delete this chat",
            )

        await self.repository.delete_chat(chat)

        return {
            "id": chat_id,
            "deleted": True,
        }

    async def reset_chat(
        self,
        user_id: int,
        chat_id: int,
    ) -> ChatDetailResponse:
        chat = await self.repository.get_chat_by_id(chat_id)

        if not chat:
            raise build_error(ErrorCode.NOT_FOUND, "chat not found")

        if chat.user_id != user_id:
            raise build_error(
                ErrorCode.FORBIDDEN,
                "You do not have permission to reset this chat",
            )

        await self.repository.reset_chat(chat)
        return await self.get_chat_detail(user_id=user_id, conversation_id=chat.id)
