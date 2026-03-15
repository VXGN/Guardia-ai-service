"""Pydantic schemas for risk analysis and safe routing."""

from pydantic import BaseModel


class CoordinatesIn(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float


class SegmentRisk(BaseModel):
    segment_id: str
    risk_score: float
    risk_factors: list[str]
    lat: float
    lng: float


class RiskAnalysisOut(BaseModel):
    overall_risk_score: float
    risk_level: str
    segments: list[SegmentRisk]
    recommendations: list[str]
    analyzed_at: str


class RoutePoint(BaseModel):
    lat: float
    lng: float


class SafeRouteOut(BaseModel):
    route: list[RoutePoint]
    total_distance_meters: float
    total_risk_score: float
    estimated_duration_seconds: float
    avoided_risk_zones: int
