"""Pydantic schemas for news scraping API."""

from datetime import datetime

from pydantic import BaseModel


class NewsArticleOut(BaseModel):
    id: str
    source: str
    title: str
    url: str
    snippet: str | None
    crime_type: str | None
    severity_score: int | None
    area: str | None
    published_at: datetime | None
    scraped_at: datetime

    model_config = {"from_attributes": True}


class ScrapeResultOut(BaseModel):
    total_scraped: int
    new_articles: int
    crime_articles: int
    analysis_synced: bool = False
    heatmap_clusters: int = 0
    message: str


class NewsListQuery(BaseModel):
    source: str | None = None
    area: str | None = None
    min_severity: int | None = None
    skip: int = 0
    limit: int = 50
