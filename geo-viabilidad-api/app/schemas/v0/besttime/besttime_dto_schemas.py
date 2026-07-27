from __future__ import annotations

from pydantic import BaseModel, Field


class BestTimeDayInfoDTO(BaseModel):
    day_int: int | None = None
    day_text: str | None = None
    day_mean: int | None = None
    day_max: int | None = None
    day_rank_mean: int | None = None
    venue_open: int | None = None
    venue_closed: int | None = None


class BestTimeDayDTO(BaseModel):
    day_info: BestTimeDayInfoDTO
    day_raw: list[int] = Field(default_factory=list)


class BestTimeForecastDTO(BaseModel):
    status: str
    message: str | None = None
    venue_info: dict | None = None
    analysis: list[BestTimeDayDTO] = Field(default_factory=list)
