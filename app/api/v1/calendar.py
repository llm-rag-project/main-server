from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.response import success_response
from app.models.school_holiday import SchoolHoliday
from app.models.user import User
from app.schemas.calendar import (
    CalendarDay,
    SchoolHolidayCreate,
    SchoolHolidayItem,
    SchoolHolidayUpdate,
    WorkWindowResponse,
)
from app.services.holiday_service import HolidayService


router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/work-window")
async def get_work_window(
    request: Request,
    target_date: date = Query(..., alias="date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await HolidayService(db).work_window(current_user.id, target_date)
    response = WorkWindowResponse(**data)
    return success_response(request=request, data=response.model_dump())


@router.get("/days")
async def list_calendar_days(
    request: Request,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    if from_date > to_date:
        raise build_error(ErrorCode.VALIDATION_ERROR, "시작일은 종료일보다 늦을 수 없습니다.")
    if (to_date - from_date).days > 62:
        raise build_error(ErrorCode.VALIDATION_ERROR, "캘린더 조회 기간은 최대 63일입니다.")
    rows = await HolidayService(db).calendar_days(current_user.id, from_date, to_date)
    return success_response(
        request=request,
        data={"items": [CalendarDay(**row).model_dump() for row in rows]},
    )


@router.get("/school-holidays")
async def list_school_holidays(
    request: Request,
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    include_inactive: bool = Query(False),
    holiday_type: str | None = Query(None, pattern="^(school|personal)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    if from_date > to_date:
        raise build_error(ErrorCode.VALIDATION_ERROR, "시작일은 종료일보다 늦을 수 없습니다.")
    if (to_date - from_date).days > 366:
        raise build_error(ErrorCode.VALIDATION_ERROR, "학교 휴일 조회 기간은 최대 1년입니다.")
    rows = await HolidayService(db).school_holidays(
        current_user.id,
        from_date,
        to_date,
        active_only=not include_inactive,
        holiday_type=holiday_type,
    )
    return success_response(
        request=request,
        data={"items": [SchoolHolidayItem.model_validate(row).model_dump() for row in rows]},
    )


@router.post("/school-holidays")
async def create_school_holiday(
    request: Request,
    body: SchoolHolidayCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    row = SchoolHoliday(user_id=current_user.id, **body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return success_response(
        request=request,
        data=SchoolHolidayItem.model_validate(row).model_dump(),
    )


@router.patch("/school-holidays/{holiday_id}")
async def update_school_holiday(
    holiday_id: int,
    request: Request,
    body: SchoolHolidayUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    row = await db.get(SchoolHoliday, holiday_id)
    if not row or row.user_id != current_user.id:
        raise build_error(ErrorCode.NOT_FOUND, "학교 휴일을 찾을 수 없습니다.")
    patch = body.model_dump(exclude_unset=True)
    start_date = patch.get("start_date", row.start_date)
    end_date = patch.get("end_date", row.end_date)
    if start_date > end_date:
        raise build_error(ErrorCode.VALIDATION_ERROR, "시작일은 종료일보다 늦을 수 없습니다.")
    if (end_date - start_date).days > 366:
        raise build_error(ErrorCode.VALIDATION_ERROR, "학교 휴일 기간은 최대 1년입니다.")
    for key, value in patch.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return success_response(
        request=request,
        data=SchoolHolidayItem.model_validate(row).model_dump(),
    )


@router.delete("/school-holidays/{holiday_id}")
async def delete_school_holiday(
    holiday_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    row = await db.get(SchoolHoliday, holiday_id)
    if not row or row.user_id != current_user.id:
        raise build_error(ErrorCode.NOT_FOUND, "학교 휴일을 찾을 수 없습니다.")
    await db.delete(row)
    await db.commit()
    return success_response(request=request, data={"deleted": True, "id": holiday_id})
