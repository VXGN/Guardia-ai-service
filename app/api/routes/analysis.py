from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.core.config import get_settings
from app.schemas.analysis_schemas import CoordinatesIn, RiskAnalysisOut, SafeRouteOut
from app.repositories.repos import SegmentRepository, RiskScoreRepository, ReportRepository, HeatmapRepository
from app.services.risk_analysis import compute_risk_scores, analyze_path_risk
from app.services.routing import calculate_safe_route
from app.services.clustering import cluster_reports

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=RiskAnalysisOut)
async def analyze_risk(
    body: CoordinatesIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    settings = get_settings()
    report_repo = ReportRepository(db)
    segment_repo = SegmentRepository(db)
    risk_repo = RiskScoreRepository(db)
    heatmap_repo = HeatmapRepository(db)

    reports = await report_repo.get_recent(settings.RISK_DECAY_DAYS)
    segments = await segment_repo.get_all()

    await compute_risk_scores(segments, reports, risk_repo)

    clusters = await cluster_reports(reports, settings.DBSCAN_EPS_KM, settings.DBSCAN_MIN_SAMPLES)
    await heatmap_repo.replace_clusters(clusters)

    result = await analyze_path_risk(
        segments, risk_repo,
        body.start_lat, body.start_lng,
        body.end_lat, body.end_lng,
    )
    return result


@router.post("/route/safe", response_model=SafeRouteOut)
async def safe_route(
    body: CoordinatesIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    segment_repo = SegmentRepository(db)
    risk_repo = RiskScoreRepository(db)

    segments = await segment_repo.get_all()
    result = await calculate_safe_route(
        segments, risk_repo,
        body.start_lat, body.start_lng,
        body.end_lat, body.end_lng,
    )
    return result
