from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import build_error, ErrorCode
from app.models.user import User
from app.repositories.keyword_repository import (
    create_keyword,
    delete_keyword,
    get_keyword_by_id,
    get_keyword_by_text,
    list_user_keywords,
    update_keyword_is_active,
)
from app.schemas.keyword import (
    BatchCreateKeywordResponse,
    BatchKeywordItemResult,
    BatchKeywordItemStatus,
    DeleteKeywordResponse,
    KeywordListItem,
    KeywordListResponse,
    KeywordResponse,
    PageInfo,
    UpdateKeywordStatusResponse,
)



async def create_user_keyword(
    db: AsyncSession,
    current_user: User,
    keyword: str,
    language: str | None = None,
) -> KeywordResponse:
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise build_error(
            ErrorCode.VALIDATION_ERROR,
            "keyword is required",
            details=[{"field": "keyword", "reason": "required"}],
        )

    existing_keyword = await get_keyword_by_text(
        db=db,
        user_id=current_user.id,
        keyword_text=normalized_keyword,
    )
    if existing_keyword is not None:
        raise build_error(
            ErrorCode.CONFLICT_DUPLICATE,
            "keyword already exists",
        )

    final_language = language or current_user.default_language

    created_keyword = await create_keyword(
        db=db,
        user_id=current_user.id,
        keyword_text=normalized_keyword,
        language=final_language,
    )

    await db.commit()

    return KeywordResponse(
        id=created_keyword.id,
        keyword=created_keyword.keyword_text,
        language=created_keyword.language,
        is_active=created_keyword.is_active,
        created_at=created_keyword.created_at,
    )
    
async def get_my_keywords(
    db: AsyncSession,
    current_user: User,
    *,
    page: int,
    size: int,
    is_active: bool | None = None,
    language: str | None = None,
    q: str | None = None,
) -> KeywordListResponse:
    items, total = await list_user_keywords(
        db=db,
        user_id=current_user.id,
        page=page,
        size=size,
        is_active=is_active,
        language=language,
        q=q,
    )

    return KeywordListResponse(
        items=[
            KeywordListItem(
                id=item.id,
                keyword=item.keyword_text,
                language=item.language,
                is_active=item.is_active,
                created_at=item.created_at,
            )
            for item in items
        ],
        page_info=PageInfo(
            page=page,
            size=size,
            total=total,
            has_next=(page * size) < total,
        ),
    )

async def patch_keyword_is_active(
    db: AsyncSession,
    current_user: User,
    *,
    keyword_id: int,
    is_active: bool,
) -> UpdateKeywordStatusResponse:
    keyword = await get_keyword_by_id(db, keyword_id)

    if keyword is None:
        raise build_error(
            ErrorCode.NOT_FOUND,
            "keyword not found",
        )

    if keyword.user_id != current_user.id:
        raise build_error(
            ErrorCode.FORBIDDEN,
            "You do not have permission to modify this keyword",
        )

    updated_keyword = await update_keyword_is_active(
        db=db,
        keyword=keyword,
        is_active=is_active,
    )
    await db.commit()

    return UpdateKeywordStatusResponse(
        id=updated_keyword.id,
        keyword=updated_keyword.keyword_text,
        language=updated_keyword.language,
        is_active=updated_keyword.is_active,
        updated_at=updated_keyword.updated_at,
    )

async def remove_keyword(
    db: AsyncSession,
    current_user: User,
    *,
    keyword_id: int,
) -> DeleteKeywordResponse:
    keyword = await get_keyword_by_id(db, keyword_id)

    if keyword is None:
        raise build_error(
            ErrorCode.NOT_FOUND,
            "keyword not found",
        )

    if keyword.user_id != current_user.id:
        raise build_error(
            ErrorCode.FORBIDDEN,
            "You do not have permission to delete this keyword",
        )

    await delete_keyword(db, keyword)
    await db.commit()

    return DeleteKeywordResponse(
        deleted=True,
        keyword_id=keyword_id,
    )

async def batch_create_user_keywords(
    db: AsyncSession,
    current_user: User,
    *,
    keywords: list[str],
    language: str | None = None,
) -> BatchCreateKeywordResponse:
    final_language = language or current_user.default_language

    seen_in_request: set[str] = set()
    created_count = 0
    skipped_count = 0
    results: list[BatchKeywordItemResult] = []

    for raw_keyword in keywords:
        if not isinstance(raw_keyword, str):
            skipped_count += 1
            results.append(
                BatchKeywordItemResult(
                    keyword=str(raw_keyword),
                    status=BatchKeywordItemStatus.FAILED_VALIDATION,
                    reason="keyword must be a string",
                )
            )
            continue

        normalized_keyword = raw_keyword.strip()
        normalized_key = normalized_keyword.lower()

        if not normalized_keyword:
            skipped_count += 1
            results.append(
                BatchKeywordItemResult(
                    keyword=raw_keyword,
                    status=BatchKeywordItemStatus.FAILED_VALIDATION,
                    reason="keyword is required",
                )
            )
            continue

        if normalized_key in seen_in_request:
            skipped_count += 1
            results.append(
                BatchKeywordItemResult(
                    keyword=normalized_keyword,
                    status=BatchKeywordItemStatus.SKIPPED_DUPLICATE,
                    reason="duplicate keyword in request",
                )
            )
            continue

        seen_in_request.add(normalized_key)

        existing_keyword = await get_keyword_by_text(
            db=db,
            user_id=current_user.id,
            keyword_text=normalized_keyword,
        )
        if existing_keyword is not None:
            skipped_count += 1
            results.append(
                BatchKeywordItemResult(
                    keyword=normalized_keyword,
                    status=BatchKeywordItemStatus.SKIPPED_ALREADY_EXISTS,
                    id=existing_keyword.id,
                    reason="keyword already exists",
                )
            )
            continue

        created_keyword = await create_keyword(
            db=db,
            user_id=current_user.id,
            keyword_text=normalized_keyword,
            language=final_language,
        )
        created_count += 1
        results.append(
            BatchKeywordItemResult(
                keyword=normalized_keyword,
                status=BatchKeywordItemStatus.CREATED,
                id=created_keyword.id,
                reason=None,
            )
        )

    await db.commit()

    return BatchCreateKeywordResponse(
        created_count=created_count,
        skipped_count=skipped_count,
        items=results,
    )