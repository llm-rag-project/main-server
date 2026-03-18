from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.repositories.chat_repository import ChatRepository
from app.schemas.chats import (
    ChatContextType,
    ChatCreateRequest,
    ChatListQuery,
    ChatSendMessageRequest,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_chat(
    payload: ChatCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(ChatRepository(db))

    try:
        result = await service.create_chat(
            user_id=current_user.id,
            payload=payload,
        )
        await db.commit()
        return success_response(data=result.model_dump())

    except ValueError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except Exception:
        await db.rollback()
        raise


@router.get("")
async def get_chats(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    context_type: ChatContextType | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(ChatRepository(db))

    try:
        query = ChatListQuery(
            page=page,
            size=size,
            q=q,
            context_type=context_type,
        )
        result = await service.get_chat_list(
            user_id=current_user.id,
            query=query,
        )
        return success_response(data=result.model_dump())

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{chat_id}")
async def get_chat_detail(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(ChatRepository(db))

    try:
        result = await service.get_chat_detail(
            user_id=current_user.id,
            chat_id=chat_id,
        )
        return success_response(data=result.model_dump())

    except ValueError as e:
        if str(e) == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="chat not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except PermissionError as e:
        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this chat",
            )
        raise


@router.post("/{chat_id}/messages")
async def send_chat_message(
    chat_id: int,
    payload: ChatSendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ChatService(ChatRepository(db))

    try:
        result = await service.send_message(
            user_id=current_user.id,
            chat_id=chat_id,
            payload=payload,
        )
        await db.commit()
        return success_response(data=result.model_dump())

    except ValueError as e:
        await db.rollback()

        if str(e) == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="chat not found",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except PermissionError as e:
        await db.rollback()

        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this chat",
            )
        raise

    except RuntimeError as e:
        await db.rollback()

        if str(e) == "UPSTREAM_ERROR":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM service temporarily unavailable",
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    except Exception:
        await db.rollback()
        raise