from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SchoolHolidayCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    holiday_type: Literal["school", "personal"] = "school"
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("school holiday period cannot exceed 366 days")
        return self


class SchoolHolidayUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    holiday_type: Literal["school", "personal"] | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None


class SchoolHolidayItem(BaseModel):
    id: int
    name: str
    holiday_type: Literal["school", "personal"]
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CalendarDay(BaseModel):
    date: date
    is_business_day: bool
    is_weekend: bool
    public_holiday_name: str | None = None
    school_holiday_names: list[str] = Field(default_factory=list)
    personal_holiday_names: list[str] = Field(default_factory=list)


class WorkWindowResponse(BaseModel):
    target_date: date
    start_date: date
    end_date: date
    is_target_business_day: bool
    days: list[CalendarDay]
