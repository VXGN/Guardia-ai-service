"""Shared analysis refresh pipeline for risk scores and heatmap clusters."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import async_session
from app.models.enums import IncidentType
from app.models.tables import IncidentReport
from app.repositories.news_repos import NewsArticleRepository, AreaCrimeScoreRepository
from app.repositories.repos import HeatmapRepository, RiskScoreRepository, SegmentRepository
from app.services.area_coordinates import get_area_coordinates
from app.services.area_risk import (
    area_risk_scores_to_heatmap_clusters,
    area_risk_scores_to_rows,
    build_area_risk_scores,
)
from app.services.clustering import cluster_reports
from app.services.crime_scorer import detect_area
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
    severity_score: int | None = None


@dataclass
class IncidentPoint:
    latitude: float
    longitude: float
    incident_type: IncidentType
    incident_at: datetime
    severity_score: int | None


def _crime_type_to_incident_type(crime_type: str | None) -> IncidentType:
    if not crime_type:
        return IncidentType.other

    text = crime_type.lower()
    if any(token in text for token in ("pencur", "theft", "rampok", "begal", "curat", "curas", "curanmor")):
        return IncidentType.theft
    if any(token in text for token in ("stalk", "menguntit", "ikuti")):
        return IncidentType.stalking
    if any(token in text for token in ("verbal", "catcall", "siul", "ucapan")):
        return IncidentType.verbal_harassment
    if any(token in text for token in ("fisik", "physical", "aniaya", "kdrt", "pukul", "kekerasan")):
        return IncidentType.physical_harassment
    if any(token in text for token in ("intimid", "ancam", "pemeras")):
        return IncidentType.intimidation
    return IncidentType.other


def _resolve_article_coordinates(article) -> tuple[float, float] | None:
    # Prefer explicit mapped area first.
    coords = get_area_coordinates(article.area)
    if coords:
        return coords

    # If area is empty, infer from article text and fallback to a known NTB center.
    inferred_area = detect_area(f"{article.title or ''} {article.snippet or ''}")
    if inferred_area:
        inferred_coords = get_area_coordinates(inferred_area)
        if inferred_coords:
            return inferred_coords

    return get_area_coordinates("Mataram")


def _build_synthetic_segments(points: list, max_segments: int = 300) -> list[dict]:
    segments: list[dict] = []
    seen_centers: set[tuple[float, float]] = set()
    offset = 0.0008

    for point in points:
        center = (round(float(point.latitude), 3), round(float(point.longitude), 3))
        if center in seen_centers:
            continue

        seen_centers.add(center)
        lat, lng = center
        segments.append(
            {
                "segment_name": f"AUTO_SEGMENT_{len(segments) + 1}",
                "start_lat": lat - offset,
                "start_lng": lng - offset,
                "end_lat": lat + offset,
                "end_lng": lng + offset,
                "length_meters": 250,
                "has_street_light": True,
                "is_main_road": True,
                "near_security_post": False,
            }
        )

        if len(segments) >= max_segments:
            break

    return segments


def _build_news_incident_points(news_articles: list) -> list[SyntheticIncidentPoint]:
    points: list[SyntheticIncidentPoint] = []
    for article in news_articles:
        coords = _resolve_article_coordinates(article)
        if not coords:
            continue

        lat, lng = coords
        points.append(
            SyntheticIncidentPoint(
                latitude=lat,
                longitude=lng,
                incident_type=_crime_type_to_incident_type(article.crime_type),
                incident_at=article.published_at or article.scraped_at or datetime.utcnow(),
                severity_score=article.severity_score or 5,
            )
        )
    return points


async def refresh_analysis_state(db: AsyncSession, settings: Settings | None = None) -> dict:
    """Recompute risk scores and heatmap clusters, then persist to DB."""
    if settings is None:
        settings = get_settings()

    segment_repo = SegmentRepository(db)
    risk_repo = RiskScoreRepository(db)
    heatmap_repo = HeatmapRepository(db)
    news_repo = NewsArticleRepository(db)
    area_risk_repo = AreaCrimeScoreRepository(db)

    cutoff = datetime.utcnow() - timedelta(days=settings.RISK_DECAY_DAYS)
    report_rows = await db.execute(
        select(
            IncidentReport.latitude,
            IncidentReport.longitude,
            IncidentReport.incident_type,
            IncidentReport.incident_at,
            IncidentReport.severity_score,
        ).where(
            IncidentReport.deleted_at.is_(None),
            IncidentReport.incident_at >= cutoff,
        )
    )
    reports = [
        IncidentPoint(
            latitude=float(row.latitude),
            longitude=float(row.longitude),
            incident_type=row.incident_type,
            incident_at=row.incident_at,
            severity_score=row.severity_score,
        )
        for row in report_rows.all()
    ]

    news_articles = await news_repo.get_recent_crime_articles(settings.RISK_DECAY_DAYS)
    news_points = _build_news_incident_points(news_articles)
    risk_points = [*reports, *news_points]

    segments = await segment_repo.get_all()
    if not segments and risk_points:
        created = await segment_repo.bulk_create(_build_synthetic_segments(risk_points))
        if created > 0:
            logger.warning(
                "road_segments was empty; auto-created %d synthetic segments from real incident coordinates",
                created,
            )
            segments = await segment_repo.get_all()

    area_scores = build_area_risk_scores(news_articles, settings.RISK_DECAY_DAYS)

    dbscan_clusters = await cluster_reports(
        risk_points,
        settings.DBSCAN_EPS_KM,
        settings.DBSCAN_MIN_SAMPLES,
    )
    area_clusters = area_risk_scores_to_heatmap_clusters(area_scores)
    clusters = [*area_clusters, *dbscan_clusters]

    await compute_risk_scores(segments, risk_points, risk_repo)
    await area_risk_repo.replace_all(area_risk_scores_to_rows(area_scores))

    # Always replace to avoid stale clusters when no cluster is produced.
    await heatmap_repo.replace_clusters(clusters)

    return {
        "recent_reports": len(reports),
        "news_points": len(news_points),
        "risk_inputs": len(risk_points),
        "area_scores": len(area_scores),
        "segments": len(segments),
        "risk_scores": await risk_repo.total_count(),
        "clusters": len(clusters),
    }


async def run_analysis_sync_job() -> dict:
    """Run refresh in its own DB session with a process-wide lock."""
    async with _analysis_sync_lock:
        async with async_session() as db:
            result = await refresh_analysis_state(db)

    logger.info(
        "Analysis sync complete: %d reports, %d news_points, %d risk_inputs, %d area_scores, %d segments, %d risk_scores, %d clusters",
        result["recent_reports"],
        result["news_points"],
        result["risk_inputs"],
        result["area_scores"],
        result["segments"],
        result["risk_scores"],
        result["clusters"],
    )
    return result
