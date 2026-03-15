from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.schemas.heatmap_schemas import HeatmapClusterOut
from app.repositories.repos import HeatmapRepository
from app.models.enums import TimeSlot

router = APIRouter(prefix="/heatmap", tags=["heatmap"])


@router.get("", response_model=list[HeatmapClusterOut])
async def get_heatmap(
    time_slot: TimeSlot | None = None,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    repo = HeatmapRepository(db)
    return await repo.get_active(time_slot)
