"""Pydantic schemas for admin dashboard."""

from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import IncidentType, TimeSlot, HeatmapIntensity


class AdminStatsOut(BaseModel):
    total_reports: int
    total_journeys: int
    active_journeys: int
    total_clusters: int
    reports_by_type: dict[str, int]
    reports_by_status: dict[str, int]


class ClusterOut(BaseModel):
    id: str
    center_lat_blurred: Decimal
    center_lng_blurred: Decimal
    radius_meters: int
    intensity: HeatmapIntensity
    incident_count: int
    dominant_type: IncidentType | None
    time_slot: TimeSlot | None

    model_config = {"from_attributes": True}


class PriorityAreaOut(BaseModel):
    segment_id: str
    segment_name: str | None
    risk_score: float
    incident_count: int
    time_slot: TimeSlot
    dominant_incident_type: IncidentType | None
