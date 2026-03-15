"""Pydantic schemas for journey tracking."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import JourneyStatus


class JourneyStartIn(BaseModel):
    user_id: str
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float


class JourneyUpdateIn(BaseModel):
    journey_id: str
    latitude: float
    longitude: float


class JourneyStopIn(BaseModel):
    journey_id: str
    safe_arrival: bool = False


class JourneyOut(BaseModel):
    id: str
    user_id: str
    status: JourneyStatus
    started_at: datetime
    ended_at: datetime | None
    origin_lat: Decimal | None
    origin_lng: Decimal | None
    destination_lat: Decimal | None
    destination_lng: Decimal | None
    safe_arrival_confirmed: bool

    model_config = {"from_attributes": True}
