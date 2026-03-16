"""create initial tables

Revision ID: 20260314_0001
Revises:
Create Date: 2026-03-14 00:01:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260314_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    user_role_enum = sa.Enum("user", "admin", "partner", name="userrole")
    incident_type_enum = sa.Enum(
        "verbal_harassment",
        "physical_harassment",
        "stalking",
        "theft",
        "intimidation",
        "other",
        name="incidenttype",
    )
    report_status_enum = sa.Enum(
        "received", "verified", "in_progress", "resolved", "rejected", name="reportstatus"
    )
    journey_status_enum = sa.Enum(
        "active", "completed", "alert_triggered", "cancelled", name="journeystatus"
    )
    time_slot_enum = sa.Enum("morning", "afternoon", "evening", "night", name="timeslot")
    heatmap_intensity_enum = sa.Enum("low", "medium", "high", "critical", name="heatmapintensity")

    # Create enum types in PostgreSQL first
    user_role_enum.create(op.get_bind(), checkfirst=True)
    incident_type_enum.create(op.get_bind(), checkfirst=True)
    report_status_enum.create(op.get_bind(), checkfirst=True)
    journey_status_enum.create(op.get_bind(), checkfirst=True)
    time_slot_enum.create(op.get_bind(), checkfirst=True)
    heatmap_intensity_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("phone_number", sa.String(length=20), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column("is_anonymous_mode", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("fcm_token", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone_number"),
    )

    op.create_table(
        "road_segments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("segment_name", sa.String(length=255), nullable=True),
        sa.Column("start_lat", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column("start_lng", sa.Numeric(precision=11, scale=8), nullable=False),
        sa.Column("end_lat", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column("end_lng", sa.Numeric(precision=11, scale=8), nullable=False),
        sa.Column("length_meters", sa.Integer(), nullable=True),
        sa.Column("has_street_light", sa.Boolean(), nullable=False),
        sa.Column("is_main_road", sa.Boolean(), nullable=False),
        sa.Column("near_security_post", sa.Boolean(), nullable=False),
        sa.Column("osm_way_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("osm_way_id"),
    )

    op.create_table(
        "heatmap_clusters",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("center_lat_blurred", sa.Numeric(precision=7, scale=5), nullable=False),
        sa.Column("center_lng_blurred", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("radius_meters", sa.Integer(), nullable=False),
        sa.Column("intensity", heatmap_intensity_enum, nullable=False),
        sa.Column("incident_count", sa.Integer(), nullable=False),
        sa.Column("dominant_type", incident_type_enum, nullable=True),
        sa.Column("time_slot", time_slot_enum, nullable=True),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "news_articles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=700), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("crime_type", sa.String(length=100), nullable=True),
        sa.Column("severity_score", sa.SmallInteger(), nullable=True),
        sa.Column("area", sa.String(length=100), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index("news_articles_source_idx", "news_articles", ["source"], unique=False)
    op.create_index("news_articles_area_idx", "news_articles", ["area"], unique=False)
    op.create_index("news_articles_severity_idx", "news_articles", ["severity_score"], unique=False)

    op.create_table(
        "area_crime_scores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("area", sa.String(length=100), nullable=False),
        sa.Column("total_articles", sa.Integer(), nullable=False),
        sa.Column("avg_severity", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("dominant_crime", sa.String(length=100), nullable=True),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("area_crime_scores_area_idx", "area_crime_scores", ["area"], unique=False)

    op.create_table(
        "incident_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("incident_type", incident_type_enum, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("incident_at", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=11, scale=8), nullable=False),
        sa.Column("latitude_blurred", sa.Numeric(precision=7, scale=5), nullable=False),
        sa.Column("longitude_blurred", sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column("location_label", sa.String(length=255), nullable=True),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False),
        sa.Column("status", report_status_enum, nullable=False),
        sa.Column("severity_score", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "incident_reports_blurred_loc_idx",
        "incident_reports",
        ["latitude_blurred", "longitude_blurred"],
        unique=False,
    )

    op.create_table(
        "journeys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("status", journey_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("origin_lat", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("origin_lng", sa.Numeric(precision=11, scale=8), nullable=True),
        sa.Column("destination_lat", sa.Numeric(precision=10, scale=8), nullable=True),
        sa.Column("destination_lng", sa.Numeric(precision=11, scale=8), nullable=True),
        sa.Column("safe_arrival_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "risk_scores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("segment_id", sa.String(length=36), nullable=False),
        sa.Column("time_slot", time_slot_enum, nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("incident_count", sa.Integer(), nullable=False),
        sa.Column("dominant_incident_type", incident_type_enum, nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["segment_id"], ["road_segments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("segment_id", "time_slot", name="risk_scores_segment_slot_uidx"),
    )

    op.create_table(
        "journey_location_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("journey_id", sa.String(length=36), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=11, scale=8), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("is_anomaly_flagged", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["journey_id"], ["journeys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("journey_location_logs")
    op.drop_table("risk_scores")
    op.drop_table("journeys")

    op.drop_index("incident_reports_blurred_loc_idx", table_name="incident_reports")
    op.drop_table("incident_reports")

    op.drop_index("area_crime_scores_area_idx", table_name="area_crime_scores")
    op.drop_table("area_crime_scores")

    op.drop_index("news_articles_severity_idx", table_name="news_articles")
    op.drop_index("news_articles_area_idx", table_name="news_articles")
    op.drop_index("news_articles_source_idx", table_name="news_articles")
    op.drop_table("news_articles")

    op.drop_table("heatmap_clusters")
    op.drop_table("road_segments")
    op.drop_table("users")

    # Drop enum types
    sa.Enum(name="heatmapintensity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="timeslot").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="journeystatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="reportstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="incidenttype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)

