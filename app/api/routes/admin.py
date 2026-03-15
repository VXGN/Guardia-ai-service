from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.schemas.admin_schemas import AdminStatsOut, ClusterOut, PriorityAreaOut
from app.repositories.repos import (
    ReportRepository, JourneyRepository, HeatmapRepository, RiskScoreRepository,
    SegmentRepository,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/statistics", response_model=AdminStatsOut)
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    report_repo = ReportRepository(db)
    journey_repo = JourneyRepository(db)
    heatmap_repo = HeatmapRepository(db)

    return AdminStatsOut(
        total_reports=await report_repo.total_count(),
        total_journeys=await journey_repo.total_count(),
        active_journeys=await journey_repo.active_count(),
        total_clusters=await heatmap_repo.total_count(),
        reports_by_type=await report_repo.count_by_type(),
        reports_by_status=await report_repo.count_by_status(),
    )


@router.get("/clusters", response_model=list[ClusterOut])
async def get_clusters(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    repo = HeatmapRepository(db)
    return await repo.get_active()


@router.get("/priorities", response_model=list[PriorityAreaOut])
async def get_priorities(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    risk_repo = RiskScoreRepository(db)
    segment_repo = SegmentRepository(db)

    high_risk = await risk_repo.get_high_risk(50.0)
    segments = await segment_repo.get_all()
    seg_map = {s.id: s for s in segments}

    result = []
    for rs in high_risk:
        seg = seg_map.get(rs.segment_id)
        result.append(PriorityAreaOut(
            segment_id=rs.segment_id,
            segment_name=seg.segment_name if seg else None,
            risk_score=float(rs.risk_score),
            incident_count=rs.incident_count,
            time_slot=rs.time_slot,
            dominant_incident_type=rs.dominant_incident_type,
        ))
    return result
