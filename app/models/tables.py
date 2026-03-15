import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, Boolean, SmallInteger, Integer, BigInteger, Numeric, DateTime, Enum, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.enums import (
    UserRole, IncidentType, ReportStatus, JourneyStatus,
    TimeSlot, HeatmapIntensity, NewsSource, NTBArea,
)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    full_name: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(150), unique=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    is_anonymous_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    fcm_token: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(6))

    incident_reports: Mapped[list["IncidentReport"]] = relationship(back_populates="user")
    journeys: Mapped[list["Journey"]] = relationship(back_populates="user")


class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    incident_type: Mapped[IncidentType] = mapped_column(Enum(IncidentType))
    description: Mapped[str | None] = mapped_column(Text)
    incident_at: Mapped[datetime] = mapped_column(DateTime(6))
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    longitude: Mapped[Decimal] = mapped_column(Numeric(11, 8))
    latitude_blurred: Mapped[Decimal] = mapped_column(Numeric(7, 5))
    longitude_blurred: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    location_label: Mapped[str | None] = mapped_column(String(255))
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.received)
    severity_score: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(6))

    user: Mapped[User | None] = relationship(back_populates="incident_reports")

    __table_args__ = (
        Index("incident_reports_blurred_loc_idx", "latitude_blurred", "longitude_blurred"),
    )


class RoadSegment(Base):
    __tablename__ = "road_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    segment_name: Mapped[str | None] = mapped_column(String(255))
    start_lat: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    start_lng: Mapped[Decimal] = mapped_column(Numeric(11, 8))
    end_lat: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    end_lng: Mapped[Decimal] = mapped_column(Numeric(11, 8))
    length_meters: Mapped[int | None] = mapped_column(Integer)
    has_street_light: Mapped[bool] = mapped_column(Boolean, default=False)
    is_main_road: Mapped[bool] = mapped_column(Boolean, default=False)
    near_security_post: Mapped[bool] = mapped_column(Boolean, default=False)
    osm_way_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow, onupdate=datetime.utcnow)

    risk_scores: Mapped[list["RiskScore"]] = relationship(back_populates="road_segment")


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    segment_id: Mapped[str] = mapped_column(String(36), ForeignKey("road_segments.id", ondelete="CASCADE"))
    time_slot: Mapped[TimeSlot] = mapped_column(Enum(TimeSlot))
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    incident_count: Mapped[int] = mapped_column(Integer, default=0)
    dominant_incident_type: Mapped[IncidentType | None] = mapped_column(Enum(IncidentType))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(6))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(6))

    road_segment: Mapped[RoadSegment] = relationship(back_populates="risk_scores")

    __table_args__ = (
        UniqueConstraint("segment_id", "time_slot", name="risk_scores_segment_slot_uidx"),
    )


class HeatmapCluster(Base):
    __tablename__ = "heatmap_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    center_lat_blurred: Mapped[Decimal] = mapped_column(Numeric(7, 5))
    center_lng_blurred: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    radius_meters: Mapped[int] = mapped_column(Integer)
    intensity: Mapped[HeatmapIntensity] = mapped_column(Enum(HeatmapIntensity))
    incident_count: Mapped[int] = mapped_column(Integer)
    dominant_type: Mapped[IncidentType | None] = mapped_column(Enum(IncidentType))
    time_slot: Mapped[TimeSlot | None] = mapped_column(Enum(TimeSlot))
    valid_from: Mapped[datetime] = mapped_column(DateTime(6))
    valid_until: Mapped[datetime] = mapped_column(DateTime(6))
    created_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow)


class Journey(Base):
    __tablename__ = "journeys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[JourneyStatus] = mapped_column(Enum(JourneyStatus), default=JourneyStatus.active)
    started_at: Mapped[datetime] = mapped_column(DateTime(6))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(6))
    origin_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    origin_lng: Mapped[Decimal | None] = mapped_column(Numeric(11, 8))
    destination_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 8))
    destination_lng: Mapped[Decimal | None] = mapped_column(Numeric(11, 8))
    safe_arrival_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="journeys")
    location_logs: Mapped[list["JourneyLocationLog"]] = relationship(back_populates="journey")


class JourneyLocationLog(Base):
    __tablename__ = "journey_location_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    journey_id: Mapped[str] = mapped_column(String(36), ForeignKey("journeys.id", ondelete="CASCADE"))
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 8))
    longitude: Mapped[Decimal] = mapped_column(Numeric(11, 8))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(6))
    is_anomaly_flagged: Mapped[bool] = mapped_column(Boolean, default=False)

    journey: Mapped[Journey] = relationship(back_populates="location_logs")


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    source: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(700), unique=True)
    snippet: Mapped[str | None] = mapped_column(Text)
    crime_type: Mapped[str | None] = mapped_column(String(100))
    severity_score: Mapped[int | None] = mapped_column(SmallInteger)
    area: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(6))
    scraped_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow)

    __table_args__ = (
        Index("news_articles_source_idx", "source"),
        Index("news_articles_area_idx", "area"),
        Index("news_articles_severity_idx", "severity_score"),
    )


class AreaCrimeScore(Base):
    __tablename__ = "area_crime_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    area: Mapped[str] = mapped_column(String(100))
    total_articles: Mapped[int] = mapped_column(Integer, default=0)
    avg_severity: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    dominant_crime: Mapped[str | None] = mapped_column(String(100))
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    period_start: Mapped[datetime] = mapped_column(DateTime(6))
    period_end: Mapped[datetime] = mapped_column(DateTime(6))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(6), default=datetime.utcnow)

    __table_args__ = (
        Index("area_crime_scores_area_idx", "area"),
    )
