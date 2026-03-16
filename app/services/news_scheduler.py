"""On-demand news scraping with in-memory cache."""

import asyncio
import logging
import time
from datetime import datetime

from app.core.database import async_session
from app.services.analysis_sync import run_analysis_sync_job
from app.services.news_scraper import scrape_all_sources, enrich_articles_with_first_paragraph
from app.services.crime_scorer import analyze_article
from app.repositories.news_repos import NewsArticleRepository

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3 * 60 * 60

_scrape_cache: dict = {"result": None, "expires_at": 0.0}
_scrape_lock = asyncio.Lock()


async def run_scrape_job(trigger_analysis_sync: bool = True) -> dict:
    """Scrape all sources, score articles, and update area scores."""
    logger.info("Starting news scrape...")

    raw_articles = await scrape_all_sources()
    raw_articles, enriched_count = await enrich_articles_with_first_paragraph(raw_articles)
    total_scraped = len(raw_articles)

    scored_articles: list[dict] = []
    for raw in raw_articles:
        analysis = analyze_article(raw.title, raw.snippet)

        if analysis.crime_type is None:
            continue

        scored_articles.append({
            "source": raw.source,
            "title": raw.title,
            "url": raw.url,
            "snippet": raw.snippet,
            "crime_type": analysis.crime_type,
            "severity_score": analysis.severity_score,
            "area": analysis.area,
            "published_at": raw.published_at,
            "scraped_at": datetime.utcnow(),
        })

    async with async_session() as db:
        article_repo = NewsArticleRepository(db)
        new_count = await article_repo.bulk_create(scored_articles)

    result = {
        "total_scraped": total_scraped,
        "new_articles": new_count,
        "crime_articles": len(scored_articles),
        "enriched_snippets": enriched_count,
        "analysis_synced": False,
        "heatmap_clusters": 0,
        "risk_scores": 0,
        "area_scores": 0,
        "segments": 0,
    }

    if trigger_analysis_sync:
        try:
            analysis_result = await run_analysis_sync_job()
            result["analysis_synced"] = True
            result["heatmap_clusters"] = analysis_result["clusters"]
            result["risk_scores"] = analysis_result["risk_scores"]
            result["area_scores"] = analysis_result["area_scores"]
            result["segments"] = analysis_result["segments"]
        except Exception:
            logger.exception("Analysis sync after scrape failed")

    logger.info(
        "Scrape complete: %d scraped, %d crime-related, %d new, analysis_synced=%s, heatmap_clusters=%d",
        total_scraped,
        len(scored_articles),
        new_count,
        result["analysis_synced"],
        result["heatmap_clusters"],
    )
    return result


async def get_or_scrape() -> dict:
    """Return cached scrape result, or scrape fresh if cache expired.

    Uses an asyncio lock to prevent concurrent scrapes when multiple
    requests hit an expired cache simultaneously.
    """
    now = time.time()
    if _scrape_cache["result"] and now < _scrape_cache["expires_at"]:
        return _scrape_cache["result"]

    async with _scrape_lock:
        now = time.time()
        if _scrape_cache["result"] and now < _scrape_cache["expires_at"]:
            return _scrape_cache["result"]

        result = await run_scrape_job()
        _scrape_cache["result"] = result
        _scrape_cache["expires_at"] = now + CACHE_TTL_SECONDS
        return result
