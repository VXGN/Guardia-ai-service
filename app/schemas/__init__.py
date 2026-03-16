"""Pydantic schemas package."""

from app.schemas.report_schemas import ReportCreate, ReportOut
from app.schemas.analysis_schemas import (
    CoordinatesIn, SegmentRisk, RiskAnalysisOut, RoutePoint, SafeRouteOut,
)
from app.schemas.heatmap_schemas import HeatmapQuery, HeatmapClusterOut, RiskScoreOut
from app.schemas.journey_schemas import (
    JourneyStartIn, JourneyUpdateIn, JourneyStopIn, JourneyOut,
)
from app.schemas.admin_schemas import AdminStatsOut, ClusterOut, PriorityAreaOut
from app.schemas.news_schemas import NewsArticleOut, ScrapeResultOut, NewsListQuery

__all__ = [
    # Reports
    "ReportCreate", "ReportOut",
    # Analysis
    "CoordinatesIn", "SegmentRisk", "RiskAnalysisOut", "RoutePoint", "SafeRouteOut",
    # Heatmap
    "HeatmapQuery", "HeatmapClusterOut", "RiskScoreOut",
    # Journey
    "JourneyStartIn", "JourneyUpdateIn", "JourneyStopIn", "JourneyOut",
    # Admin
    "AdminStatsOut", "ClusterOut", "PriorityAreaOut",
    # News
    "NewsArticleOut", "ScrapeResultOut", "NewsListQuery",
]
