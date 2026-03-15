"""Pydantic schemas for heatmap and risk scores."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import IncidentType, TimeSlot, HeatmapIntensity


class HeatmapQuery(BaseModel):
    lat: float | None = None
    lng: float | None = None
    radius: float | None = None
    time_slot: TimeSlot | None = None


class HeatmapClusterOut(BaseModel):
    id: str
    center_lat_blurred: Decimal
    center_lng_blurred: Decimal
    radius_meters: int
    intensity: HeatmapIntensity
    incident_count: int
    dominant_type: IncidentType | None
    time_slot: TimeSlot | None
    valid_from: datetime
    valid_until: datetime

    model_config = {"from_attributes": True}


class RiskScoreOut(BaseModel):
    id: str
    segment_id: str
    time_slot: TimeSlot
    risk_score: Decimal
    incident_count: int
    dominant_incident_type: IncidentType | None

    model_config = {"from_attributes": True}
