"""Pydantic schemas for incident reports."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import IncidentType, ReportStatus


class ReportCreate(BaseModel):
    incident_type: IncidentType
    description: str | None = None
    incident_at: datetime
    latitude: Decimal = Field(decimal_places=8)
    longitude: Decimal = Field(decimal_places=8)
    location_label: str | None = None
    is_anonymous: bool = True
    severity_score: int | None = None


class ReportOut(BaseModel):
    id: str
    user_id: str | None
    incident_type: IncidentType
    description: str | None
    incident_at: datetime
    latitude_blurred: Decimal
    longitude_blurred: Decimal
    location_label: str | None
    is_anonymous: bool
    status: ReportStatus
    severity_score: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
