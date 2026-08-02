from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import holidays
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school_holiday import SchoolHoliday


MAX_WORK_WINDOW_DAYS = 45
KST = ZoneInfo("Asia/Seoul")


def article_collection_window(
    start_date: date,
    end_date: date,
    send_time: str = "08:30",
) -> tuple[datetime, datetime]:
    """Return the publication window represented by one or more mail dates."""
    if start_date > end_date:
        raise ValueError("start_date must be less than or equal to end_date")
    try:
        hour, minute = (int(part) for part in send_time.split(":", 1))
        boundary = time(hour=hour, minute=minute)
    except (AttributeError, TypeError, ValueError):
        boundary = time(hour=8, minute=30)
    return (
        datetime.combine(start_date - timedelta(days=1), boundary, tzinfo=KST),
        datetime.combine(end_date, boundary, tzinfo=KST),
    )


def calculate_collection_start(
    target_date: date,
    non_business_dates: set[date],
    *,
    max_lookback_days: int = MAX_WORK_WINDOW_DAYS,
) -> date:
    """Return the first date that should be reviewed on a business-day dashboard."""
    if target_date in non_business_dates:
        return target_date

    start_date = target_date
    cursor = target_date - timedelta(days=1)
    inspected = 0
    while cursor in non_business_dates and inspected < max_lookback_days:
        start_date = cursor
        cursor -= timedelta(days=1)
        inspected += 1
    return start_date


class HolidayService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _public_holidays(start_date: date, end_date: date) -> dict[date, str]:
        years = range(start_date.year, end_date.year + 1)
        calendar = holidays.country_holidays("KR", years=years, language="ko")
        return {
            day: str(name)
            for day, name in calendar.items()
            if start_date <= day <= end_date
        }

    async def school_holidays(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
        *,
        active_only: bool = True,
        holiday_type: str | None = None,
    ) -> list[SchoolHoliday]:
        stmt = (
            select(SchoolHoliday)
            .where(
                SchoolHoliday.user_id == user_id,
                SchoolHoliday.start_date <= end_date,
                SchoolHoliday.end_date >= start_date,
            )
            .order_by(SchoolHoliday.start_date, SchoolHoliday.id)
        )
        if active_only:
            stmt = stmt.where(SchoolHoliday.is_active.is_(True))
        if holiday_type:
            stmt = stmt.where(SchoolHoliday.holiday_type == holiday_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def calendar_days(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        if start_date > end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        if (end_date - start_date).days > 366:
            raise ValueError("calendar range cannot exceed 366 days")

        public = self._public_holidays(start_date, end_date)
        school_periods = await self.school_holidays(user_id, start_date, end_date)
        rows = []
        cursor = start_date
        while cursor <= end_date:
            school_names = [
                item.name
                for item in school_periods
                if item.holiday_type == "school"
                and item.start_date <= cursor <= item.end_date
            ]
            personal_names = [
                item.name
                for item in school_periods
                if item.holiday_type == "personal"
                and item.start_date <= cursor <= item.end_date
            ]
            is_weekend = cursor.weekday() >= 5
            public_name = public.get(cursor)
            rows.append(
                {
                    "date": cursor,
                    "is_business_day": not (is_weekend or public_name or school_names or personal_names),
                    "is_weekend": is_weekend,
                    "public_holiday_name": public_name,
                    "school_holiday_names": school_names,
                    "personal_holiday_names": personal_names,
                }
            )
            cursor += timedelta(days=1)
        return rows

    async def work_window(self, user_id: int, target_date: date) -> dict:
        lookback_start = target_date - timedelta(days=MAX_WORK_WINDOW_DAYS)
        days = await self.calendar_days(user_id, lookback_start, target_date)
        by_date = {row["date"]: row for row in days}
        non_business = {
            day
            for day, row in by_date.items()
            if not row["is_business_day"]
        }
        start_date = calculate_collection_start(target_date, non_business)
        selected_days = [
            by_date[start_date + timedelta(days=offset)]
            for offset in range((target_date - start_date).days + 1)
        ]
        return {
            "target_date": target_date,
            "start_date": start_date,
            "end_date": target_date,
            "is_target_business_day": by_date[target_date]["is_business_day"],
            "days": selected_days,
        }
