from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tables import (
    IncidentReport, RoadSegment, RiskScore, HeatmapCluster,
    Journey, JourneyLocationLog,
)
from app.models.enums import IncidentType, TimeSlot, JourneyStatus


class ReportRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: str | None, **kwargs) -> IncidentReport:
        lat = kwargs["latitude"]
        lng = kwargs["longitude"]
        blurred_lat = Decimal(str(round(float(lat), 3)))
        blurred_lng = Decimal(str(round(float(lng), 3)))
        report = IncidentReport(
            user_id=user_id,
            latitude_blurred=blurred_lat,
            longitude_blurred=blurred_lng,
            **kwargs,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_by_id(self, report_id: str) -> IncidentReport | None:
        result = await self.db.execute(
            select(IncidentReport).where(
                IncidentReport.id == report_id,
                IncidentReport.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_reports(self, skip: int = 0, limit: int = 50) -> list[IncidentReport]:
        result = await self.db.execute(
            select(IncidentReport)
            .where(IncidentReport.deleted_at.is_(None))
            .order_by(IncidentReport.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent(self, days: int = 30) -> list[IncidentReport]:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            select(IncidentReport).where(
                IncidentReport.deleted_at.is_(None),
                IncidentReport.incident_at >= cutoff,
            )
        )
        return list(result.scalars().all())

    async def count_by_type(self) -> dict[str, int]:
        result = await self.db.execute(
            select(IncidentReport.incident_type, func.count())
            .where(IncidentReport.deleted_at.is_(None))
            .group_by(IncidentReport.incident_type)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def count_by_status(self) -> dict[str, int]:
        result = await self.db.execute(
            select(IncidentReport.status, func.count())
            .where(IncidentReport.deleted_at.is_(None))
            .group_by(IncidentReport.status)
        )
        return {row[0].value: row[1] for row in result.all()}

    async def total_count(self) -> int:
        result = await self.db.execute(
            select(func.count()).where(IncidentReport.deleted_at.is_(None))
        )
        return result.scalar_one()


class SegmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> list[RoadSegment]:
        result = await self.db.execute(select(RoadSegment))
        return list(result.scalars().all())

    async def get_nearby(self, lat: float, lng: float, radius_deg: float = 0.01) -> list[RoadSegment]:
        result = await self.db.execute(
            select(RoadSegment).where(
                and_(
                    RoadSegment.start_lat.between(lat - radius_deg, lat + radius_deg),
                    RoadSegment.start_lng.between(lng - radius_deg, lng + radius_deg),
                )
            )
        )
        return list(result.scalars().all())


class RiskScoreRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, segment_id: str, time_slot: TimeSlot, score: float, count: int, dominant: IncidentType | None):
        existing = await self.db.execute(
            select(RiskScore).where(
                RiskScore.segment_id == segment_id,
                RiskScore.time_slot == time_slot,
            )
        )
        row = existing.scalar_one_or_none()
        now = datetime.utcnow()
        if row:
            row.risk_score = Decimal(str(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            row.incident_count = count
            row.dominant_incident_type = dominant
            row.calculated_at = now
        else:
            row = RiskScore(
                segment_id=segment_id,
                time_slot=time_slot,
                risk_score=Decimal(str(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                incident_count=count,
                dominant_incident_type=dominant,
                calculated_at=now,
            )
            self.db.add(row)
        await self.db.commit()

    async def get_by_segment(self, segment_id: str) -> list[RiskScore]:
        result = await self.db.execute(
            select(RiskScore).where(RiskScore.segment_id == segment_id)
        )
        return list(result.scalars().all())

    async def get_high_risk(self, min_score: float = 50.0) -> list[RiskScore]:
        result = await self.db.execute(
            select(RiskScore)
            .where(RiskScore.risk_score >= min_score)
            .order_by(RiskScore.risk_score.desc())
        )
        return list(result.scalars().all())


class HeatmapRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active(self, time_slot: TimeSlot | None = None) -> list[HeatmapCluster]:
        now = datetime.utcnow()
        q = select(HeatmapCluster).where(HeatmapCluster.valid_until >= now)
        if time_slot:
            q = q.where(HeatmapCluster.time_slot == time_slot)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def replace_clusters(self, clusters: list[HeatmapCluster]):
        await self.db.execute(
            HeatmapCluster.__table__.delete()
        )
        for c in clusters:
            self.db.add(c)
        await self.db.commit()

    async def total_count(self) -> int:
        result = await self.db.execute(select(func.count(HeatmapCluster.id)))
        return result.scalar_one()


class JourneyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **kwargs) -> Journey:
        journey = Journey(**kwargs)
        self.db.add(journey)
        await self.db.commit()
        await self.db.refresh(journey)
        return journey

    async def get_by_id(self, journey_id: str) -> Journey | None:
        result = await self.db.execute(
            select(Journey).where(Journey.id == journey_id)
        )
        return result.scalar_one_or_none()

    async def update_status(self, journey_id: str, status: JourneyStatus, **kwargs):
        journey = await self.get_by_id(journey_id)
        if journey:
            journey.status = status
            for k, v in kwargs.items():
                setattr(journey, k, v)
            await self.db.commit()
        return journey

    async def add_location_log(self, journey_id: str, lat: float, lng: float) -> JourneyLocationLog:
        log = JourneyLocationLog(
            journey_id=journey_id,
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lng)),
            recorded_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.commit()
        return log

    async def total_count(self) -> int:
        result = await self.db.execute(select(func.count(Journey.id)))
        return result.scalar_one()

    async def active_count(self) -> int:
        result = await self.db.execute(
            select(func.count()).where(Journey.status == JourneyStatus.active)
        )
        return result.scalar_one()
