"""Shared analysis refresh pipeline for risk scores and heatmap clusters."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import async_session
from app.models.enums import IncidentType
from app.repositories.news_repos import NewsArticleRepository
from app.repositories.repos import HeatmapRepository, ReportRepository, RiskScoreRepository, SegmentRepository
from app.services.area_coordinates import get_area_coordinates
from app.services.clustering import cluster_reports
from app.services.risk_analysis import compute_risk_scores

logger = logging.getLogger(__name__)
_analysis_sync_lock = asyncio.Lock()


@dataclass
class SyntheticIncidentPoint:
    """Lightweight point model for clustering news by mapped area coordinates."""

    latitude: float
    longitude: float
    incident_type: IncidentType
    incident_at: datetime


def _build_news_incident_points(news_articles: list) -> list[SyntheticIncidentPoint]:
    points: list[SyntheticIncidentPoint] = []
    for article in news_articles:
        coords = get_area_coordinates(article.area)
        if not coords:
            continue

        lat, lng = coords
        points.append(
            SyntheticIncidentPoint(
                latitude=lat,
                longitude=lng,
                incident_type=IncidentType.other,
                incident_at=article.published_at or article.scraped_at,
            )
        )
    return points


async def refresh_analysis_state(db: AsyncSession, settings: Settings | None = None) -> dict:
    """Recompute risk scores and heatmap clusters, then persist to DB."""
    if settings is None:
        settings = get_settings()

    report_repo = ReportRepository(db)
    segment_repo = SegmentRepository(db)
    risk_repo = RiskScoreRepository(db)
    heatmap_repo = HeatmapRepository(db)
    news_repo = NewsArticleRepository(db)

    reports = await report_repo.get_recent(settings.RISK_DECAY_DAYS)
    segments = await segment_repo.get_all()
    news_articles = await news_repo.get_recent_crime_articles(settings.RISK_DECAY_DAYS)
    news_points = _build_news_incident_points(news_articles)

    await compute_risk_scores(segments, reports, risk_repo)

    clusters = await cluster_reports(
        [*reports, *news_points],
        settings.DBSCAN_EPS_KM,
        settings.DBSCAN_MIN_SAMPLES,
    )
    # Always replace to avoid stale clusters when no cluster is produced.
    await heatmap_repo.replace_clusters(clusters)

    return {
        "recent_reports": len(reports),
        "news_points": len(news_points),
        "segments": len(segments),
        "clusters": len(clusters),
    }


async def run_analysis_sync_job() -> dict:
    """Run refresh in its own DB session with a process-wide lock."""
    async with _analysis_sync_lock:
        async with async_session() as db:
            result = await refresh_analysis_state(db)

    logger.info(
        "Analysis sync complete: %d reports, %d news_points, %d segments, %d clusters",
        result["recent_reports"],
        result["news_points"],
        result["segments"],
        result["clusters"],
    )
    return result
