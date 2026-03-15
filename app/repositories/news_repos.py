"""Repositories for news articles and area crime scores."""

from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, func, delete
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

    async def replace_scores(self, scores: list[dict]):
        """Delete all existing scores and insert new ones."""
        await self.db.execute(delete(AreaCrimeScore))
        for data in scores:
            self.db.add(AreaCrimeScore(**data))
        await self.db.commit()

    async def get_all(self) -> list[AreaCrimeScore]:
        result = await self.db.execute(
            select(AreaCrimeScore).order_by(AreaCrimeScore.score.desc())
        )
        return list(result.scalars().all())

    async def get_by_area(self, area: str) -> AreaCrimeScore | None:
        result = await self.db.execute(
            select(AreaCrimeScore).where(AreaCrimeScore.area == area)
        )
        return result.scalar_one_or_none()

    async def calculate_and_store(self, articles: list[NewsArticle], days: int = 30):
        """Calculate area crime scores from articles and store them."""
        now = datetime.utcnow()
        period_start = now - timedelta(days=days)

        area_articles: dict[str, list[NewsArticle]] = {}
        for article in articles:
            if article.area and article.severity_score is not None:
                area_articles.setdefault(article.area, []).append(article)

        scores: list[dict] = []
        for area, area_arts in area_articles.items():
            total = len(area_arts)
            severities = [a.severity_score for a in area_arts if a.severity_score]
            avg_sev = sum(severities) / len(severities) if severities else 0

            crime_types = [a.crime_type for a in area_arts if a.crime_type]
            dominant = Counter(crime_types).most_common(1)[0][0] if crime_types else None

            composite = min(
                Decimal("100"),
                Decimal(str(total * 2)) + Decimal(str(avg_sev * 5)),
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            scores.append({
                "area": area,
                "total_articles": total,
                "avg_severity": Decimal(str(avg_sev)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                "dominant_crime": dominant,
                "score": composite,
                "period_start": period_start,
                "period_end": now,
                "calculated_at": now,
            })

        await self.replace_scores(scores)
        return scores
