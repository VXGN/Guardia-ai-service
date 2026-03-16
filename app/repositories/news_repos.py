"""Repositories for news articles."""

from datetime import datetime, timedelta

from sqlalchemy import select, func, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import NewsArticle, AreaCrimeScore


class NewsArticleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def url_exists(self, url: str) -> bool:
        result = await self.db.execute(
            select(func.count()).select_from(NewsArticle).where(NewsArticle.url == url)
        )
        return result.scalar_one() > 0

    async def create(self, **kwargs) -> NewsArticle:
        article = NewsArticle(**kwargs)
        self.db.add(article)
        await self.db.commit()
        await self.db.refresh(article)
        return article

    async def bulk_create(self, articles: list[dict]) -> int:
        """Create multiple articles, skipping duplicates by URL. Returns count of new articles."""
        created = 0
        for data in articles:
            exists = await self.url_exists(data["url"])
            if not exists:
                article = NewsArticle(**data)
                self.db.add(article)
                created += 1
        if created > 0:
            await self.db.commit()
        return created

    async def list_articles(
        self,
        source: str | None = None,
        area: str | None = None,
        min_severity: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[NewsArticle]:
        q = select(NewsArticle).where(NewsArticle.severity_score.is_not(None))

        if source:
            q = q.where(NewsArticle.source == source)
        if area:
            q = q.where(NewsArticle.area == area)
        if min_severity is not None:
            q = q.where(NewsArticle.severity_score >= min_severity)

        q = q.order_by(NewsArticle.scraped_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_articles_for_area(
        self, area: str, days: int = 30
    ) -> list[NewsArticle]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            select(NewsArticle).where(
                NewsArticle.area == area,
                NewsArticle.severity_score.is_not(None),
                NewsArticle.scraped_at >= cutoff,
            ).order_by(NewsArticle.scraped_at.desc())
        )
        return list(result.scalars().all())

    async def get_recent_crime_articles(self, days: int = 30) -> list[NewsArticle]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            select(NewsArticle).where(
                NewsArticle.severity_score.is_not(None),
                NewsArticle.scraped_at >= cutoff,
            )
        )
        return list(result.scalars().all())

    async def count_articles(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(NewsArticle).where(
                NewsArticle.severity_score.is_not(None)
            )
        )
        return result.scalar_one()


class AreaCrimeScoreRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _create_table_if_missing(self):
        await self.db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS area_crime_scores (
                    id VARCHAR(36) PRIMARY KEY,
                    area VARCHAR(100) NOT NULL,
                    total_articles INTEGER NOT NULL,
                    avg_severity NUMERIC(5, 2) NOT NULL,
                    dominant_crime VARCHAR(100),
                    score NUMERIC(5, 2) NOT NULL,
                    period_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    period_end TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    calculated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
                );
                """
            )
        )
        await self.db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS area_crime_scores_area_idx
                ON area_crime_scores (area);
                """
            )
        )
        await self.db.commit()

    async def replace_all(self, rows: list[dict]) -> int:
        try:
            await self.db.execute(AreaCrimeScore.__table__.delete())
        except ProgrammingError as exc:
            if "area_crime_scores" not in str(exc):
                raise
            await self.db.rollback()
            await self._create_table_if_missing()
            await self.db.execute(AreaCrimeScore.__table__.delete())

        for row in rows:
            self.db.add(AreaCrimeScore(**row))
        await self.db.commit()
        return len(rows)

    async def list_latest(self, limit: int = 50) -> list[AreaCrimeScore]:
        try:
            result = await self.db.execute(
                select(AreaCrimeScore)
                .order_by(AreaCrimeScore.score.desc(), AreaCrimeScore.total_articles.desc())
                .limit(limit)
            )
        except ProgrammingError as exc:
            if "area_crime_scores" not in str(exc):
                raise
            await self.db.rollback()
            await self._create_table_if_missing()
            result = await self.db.execute(
                select(AreaCrimeScore)
                .order_by(AreaCrimeScore.score.desc(), AreaCrimeScore.total_articles.desc())
                .limit(limit)
            )

        return list(result.scalars().all())
