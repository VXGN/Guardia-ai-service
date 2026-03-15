"""Pydantic schemas for news scraping API."""

from datetime import datetime
from decimal import Decimal

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


class AreaCrimeScoreOut(BaseModel):
    id: str
    area: str
    total_articles: int
    avg_severity: Decimal
    dominant_crime: str | None
    score: Decimal
    period_start: datetime
    period_end: datetime
    calculated_at: datetime

    model_config = {"from_attributes": True}


class AreaDetailOut(BaseModel):
    score: AreaCrimeScoreOut | None = None
    recent_articles: list[NewsArticleOut]


class ScrapeResultOut(BaseModel):
    total_scraped: int
    new_articles: int
    crime_articles: int
    message: str


class NewsListQuery(BaseModel):
    source: str | None = None
    area: str | None = None
    min_severity: int | None = None
    skip: int = 0
    limit: int = 50
