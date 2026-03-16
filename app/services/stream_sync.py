"""Background sync workers to keep online DB data fresh."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.core.config import get_settings
from app.core.database import async_session
from app.repositories.repos import HeatmapRepository, ReportRepository, RiskScoreRepository, SegmentRepository
from app.services.clustering import cluster_reports
from app.services.news_scheduler import run_scrape_job
from app.services.risk_analysis import compute_risk_scores

logger = logging.getLogger(__name__)


async def run_analysis_sync_job() -> dict:
    """Recompute risk scores and heatmap clusters, then persist to DB."""
    settings = get_settings()

    async with async_session() as db:
        report_repo = ReportRepository(db)
        segment_repo = SegmentRepository(db)
        risk_repo = RiskScoreRepository(db)
        heatmap_repo = HeatmapRepository(db)

        reports = await report_repo.get_recent(settings.RISK_DECAY_DAYS)
        segments = await segment_repo.get_all()

        await compute_risk_scores(segments, reports, risk_repo)

        clusters = await cluster_reports(
            reports,
            settings.DBSCAN_EPS_KM,
            settings.DBSCAN_MIN_SAMPLES,
        )
        # Always replace to avoid stale clusters when no cluster is produced.
        await heatmap_repo.replace_clusters(clusters)

    result = {
        "recent_reports": len(reports),
        "segments": len(segments),
        "clusters": len(clusters),
    }
    logger.info(
        "Analysis sync complete: %d reports, %d segments, %d clusters",
        result["recent_reports"],
        result["segments"],
        result["clusters"],
    )
    return result


async def _run_loop(
    name: str,
    interval_seconds: int,
    job: Callable[[], Awaitable[dict]],
    stop_event: asyncio.Event,
    run_on_startup: bool,
):
    if run_on_startup:
        try:
            await job()
        except Exception:
            logger.exception("%s startup sync failed", name)

    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(5, interval_seconds))
            break
        except TimeoutError:
            pass

        try:
            await job()
        except Exception:
            logger.exception("%s periodic sync failed", name)


def start_background_sync(stop_event: asyncio.Event) -> list[asyncio.Task]:
    """Create background tasks for periodic news and analysis sync."""
    settings = get_settings()
    tasks: list[asyncio.Task] = []

    news_task = asyncio.create_task(
        _run_loop(
            name="news",
            interval_seconds=settings.NEWS_SYNC_INTERVAL_SECONDS,
            job=run_scrape_job,
            stop_event=stop_event,
            run_on_startup=settings.RUN_SYNC_ON_STARTUP,
        )
    )
    tasks.append(news_task)

    analysis_task = asyncio.create_task(
        _run_loop(
            name="analysis",
            interval_seconds=settings.ANALYSIS_SYNC_INTERVAL_SECONDS,
            job=run_analysis_sync_job,
            stop_event=stop_event,
            run_on_startup=settings.RUN_SYNC_ON_STARTUP,
        )
    )
    tasks.append(analysis_task)

    logger.info(
        "Background sync enabled (news=%ss, analysis=%ss)",
        settings.NEWS_SYNC_INTERVAL_SECONDS,
        settings.ANALYSIS_SYNC_INTERVAL_SECONDS,
    )
    return tasks
