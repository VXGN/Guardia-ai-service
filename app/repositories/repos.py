from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select, func, and_, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine
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

    async def bulk_create(self, segments: list[dict]) -> int:
        if not segments:
            return 0

        rows = [RoadSegment(**segment) for segment in segments]
        self.db.add_all(rows)
        await self.db.commit()
        return len(rows)


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
        valid_until = now + timedelta(hours=6)
        if row:
            row.risk_score = Decimal(str(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            row.incident_count = count
            row.dominant_incident_type = dominant
            row.calculated_at = now
            row.valid_until = valid_until
        else:
            row = RiskScore(
                segment_id=segment_id,
                time_slot=time_slot,
                risk_score=Decimal(str(score)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                incident_count=count,
                dominant_incident_type=dominant,
                calculated_at=now,
                valid_until=valid_until,
            )
            self.db.add(row)

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

    async def total_count(self) -> int:
        result = await self.db.execute(select(func.count(RiskScore.id)))
        return result.scalar_one()


class HeatmapRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_postgres_enums(self):
        """Create required enum types if missing in PostgreSQL."""
        bind = self.db.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            return

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        CREATE TYPE incidenttype AS ENUM (
                            'verbal_harassment',
                            'physical_harassment',
                            'stalking',
                            'theft',
                            'intimidation',
                            'other'
                        );
                    EXCEPTION
                        WHEN duplicate_object THEN NULL;
                    END
                    $$;
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        CREATE TYPE timeslot AS ENUM ('morning', 'afternoon', 'evening', 'night');
                    EXCEPTION
                        WHEN duplicate_object THEN NULL;
                    END
                    $$;
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        CREATE TYPE heatmapintensity AS ENUM ('low', 'medium', 'high', 'critical');
                    EXCEPTION
                        WHEN duplicate_object THEN NULL;
                    END
                    $$;
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    DO $$
                    DECLARE
                        intensity_typ text;
                        dominant_typ text;
                        slot_typ text;
                        risk_slot_typ text;
                        risk_dom_typ text;
                    BEGIN
                        SELECT t.typname INTO intensity_typ
                        FROM pg_attribute a
                        JOIN pg_class c ON c.oid = a.attrelid
                        JOIN pg_type t ON t.oid = a.atttypid
                        WHERE c.relname = 'heatmap_clusters'
                          AND a.attname = 'intensity'
                          AND a.attnum > 0
                          AND NOT a.attisdropped;

                        IF intensity_typ = 'HeatmapIntensity' THEN
                            ALTER TABLE heatmap_clusters
                            ALTER COLUMN intensity TYPE heatmapintensity
                            USING intensity::text::heatmapintensity;
                        END IF;

                        SELECT t.typname INTO dominant_typ
                        FROM pg_attribute a
                        JOIN pg_class c ON c.oid = a.attrelid
                        JOIN pg_type t ON t.oid = a.atttypid
                        WHERE c.relname = 'heatmap_clusters'
                          AND a.attname = 'dominant_type'
                          AND a.attnum > 0
                          AND NOT a.attisdropped;

                        IF dominant_typ = 'IncidentType' THEN
                            ALTER TABLE heatmap_clusters
                            ALTER COLUMN dominant_type TYPE incidenttype
                            USING dominant_type::text::incidenttype;
                        END IF;

                        SELECT t.typname INTO slot_typ
                        FROM pg_attribute a
                        JOIN pg_class c ON c.oid = a.attrelid
                        JOIN pg_type t ON t.oid = a.atttypid
                        WHERE c.relname = 'heatmap_clusters'
                          AND a.attname = 'time_slot'
                          AND a.attnum > 0
                          AND NOT a.attisdropped;

                        IF slot_typ = 'TimeSlot' THEN
                            ALTER TABLE heatmap_clusters
                            ALTER COLUMN time_slot TYPE timeslot
                            USING time_slot::text::timeslot;
                        END IF;

                        SELECT t.typname INTO risk_slot_typ
                        FROM pg_attribute a
                        JOIN pg_class c ON c.oid = a.attrelid
                        JOIN pg_type t ON t.oid = a.atttypid
                        WHERE c.relname = 'risk_scores'
                          AND a.attname = 'time_slot'
                          AND a.attnum > 0
                          AND NOT a.attisdropped;

                        IF risk_slot_typ = 'TimeSlot' THEN
                            ALTER TABLE risk_scores
                            ALTER COLUMN time_slot TYPE timeslot
                            USING time_slot::text::timeslot;
                        END IF;

                        SELECT t.typname INTO risk_dom_typ
                        FROM pg_attribute a
                        JOIN pg_class c ON c.oid = a.attrelid
                        JOIN pg_type t ON t.oid = a.atttypid
                        WHERE c.relname = 'risk_scores'
                          AND a.attname = 'dominant_incident_type'
                          AND a.attnum > 0
                          AND NOT a.attisdropped;

                        IF risk_dom_typ = 'IncidentType' THEN
                            ALTER TABLE risk_scores
                            ALTER COLUMN dominant_incident_type TYPE incidenttype
                            USING dominant_incident_type::text::incidenttype;
                        END IF;
                    END
                    $$;
                    """
                )
            )

    async def get_active(self, time_slot: TimeSlot | None = None) -> list[HeatmapCluster]:
        now = datetime.utcnow()
        q = select(HeatmapCluster).where(HeatmapCluster.valid_until >= now)
        if time_slot:
            q = q.where(HeatmapCluster.time_slot == time_slot)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def replace_clusters(self, clusters: list[HeatmapCluster]):
        await self._ensure_postgres_enums()

        try:
            await self.db.execute(HeatmapCluster.__table__.delete())
            for c in clusters:
                self.db.add(c)
            await self.db.commit()
        except ProgrammingError as exc:
            # Retry once after forcing enum bootstrap; covers missing types
            # and legacy enum name mismatches.
            error_text = str(exc)
            if (
                "does not exist" not in error_text
                and "heatmapintensity" not in error_text
                and "datatype mismatch" not in error_text.lower()
            ):
                raise

            await self.db.rollback()
            await self._ensure_postgres_enums()

            await self.db.execute(HeatmapCluster.__table__.delete())
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
