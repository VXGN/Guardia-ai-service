"""API routes for news scraping."""

import asyncio
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.repositories.news_repos import NewsArticleRepository
from app.schemas.news_schemas import NewsArticleOut, ScrapeResultOut
from app.services.news_scheduler import run_scrape_job

router = APIRouter(prefix="/news", tags=["news"])
logger = logging.getLogger(__name__)


@router.get("/articles", response_model=list[NewsArticleOut])
async def list_articles(
    source: str | None = Query(None, description="Filter by source (detik, kompas, insidelombok, postlombok)"),
    area: str | None = Query(None, description="Filter by NTB area name"),
    min_severity: int | None = Query(None, ge=1, le=10, description="Minimum severity score"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List scraped crime news articles with optional filters."""
    repo = NewsArticleRepository(db)
    articles = await repo.list_articles(
        source=source,
        area=area,
        min_severity=min_severity,
        skip=skip,
        limit=limit,
    )
    return [NewsArticleOut.model_validate(a) for a in articles]


@router.post("/scrape", response_model=ScrapeResultOut)
async def trigger_scrape(_: dict = Depends(verify_firebase_token)):
    """Manually trigger a news scrape (admin use)."""
    try:
        result = await asyncio.wait_for(run_scrape_job(), timeout=120)
    except Exception:
        logger.exception("Manual /news/scrape failed")
        result = {
            "total_scraped": 0,
            "new_articles": 0,
            "crime_articles": 0,
        }
        return ScrapeResultOut(
            total_scraped=result["total_scraped"],
            new_articles=result["new_articles"],
            crime_articles=result["crime_articles"],
            message="Scrape failed. Check server logs.",
        )

    return ScrapeResultOut(
        total_scraped=result["total_scraped"],
        new_articles=result["new_articles"],
        crime_articles=result["crime_articles"],
        message="Scrape completed successfully",
    )
