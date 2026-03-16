"""create missing enum types

Revision ID: 20260316_0002
Revises: 20260314_0001
Create Date: 2026-03-16 00:01:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260316_0002"
down_revision: Union[str, Sequence[str], None] = "20260314_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create any missing enum types that weren't properly created."""
    # These enums should have been created by the initial migration
    # Using checkfirst=True to avoid errors if they already exist
    sa.Enum("user", "admin", "partner", name="userrole").create(op.get_bind(), checkfirst=True)
    sa.Enum(
        "verbal_harassment",
        "physical_harassment",
        "stalking",
        "theft",
        "intimidation",
        "other",
        name="incidenttype",
    ).create(op.get_bind(), checkfirst=True)
    sa.Enum(
        "received", "verified", "in_progress", "resolved", "rejected", name="reportstatus"
    ).create(op.get_bind(), checkfirst=True)
    sa.Enum(
        "active", "completed", "alert_triggered", "cancelled", name="journeystatus"
    ).create(op.get_bind(), checkfirst=True)
    sa.Enum("morning", "afternoon", "evening", "night", name="timeslot").create(
        op.get_bind(), checkfirst=True
    )
    sa.Enum("low", "medium", "high", "critical", name="heatmapintensity").create(
        op.get_bind(), checkfirst=True
    )


def downgrade() -> None:
    """No-op downgrade - we don't want to remove enums that tables depend on."""
    pass
