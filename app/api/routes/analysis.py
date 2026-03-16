from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.core.config import get_settings
from app.schemas.analysis_schemas import CoordinatesIn, RiskAnalysisOut, SafeRouteOut
from app.repositories.repos import SegmentRepository, RiskScoreRepository
from app.repositories.news_repos import NewsArticleRepository
from app.services.risk_analysis import analyze_path_risk
from app.services.routing import calculate_safe_route
from app.services.analysis_sync import refresh_analysis_state
from app.services.area_coordinates import get_area_coordinates

router = APIRouter(tags=["analysis"])


@router.post("/analyze", response_model=RiskAnalysisOut)
async def analyze_risk(
    body: CoordinatesIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    settings = get_settings()
    await refresh_analysis_state(db, settings)

    segment_repo = SegmentRepository(db)
    risk_repo = RiskScoreRepository(db)
    news_repo = NewsArticleRepository(db)

    segments = await segment_repo.get_all()
    news_articles = await news_repo.get_recent_crime_articles(settings.RISK_DECAY_DAYS)

    result = await analyze_path_risk(
        segments, risk_repo,
        body.start_lat, body.start_lng,
        body.end_lat, body.end_lng,
    )
    news_locations = []
    for article in news_articles:
        coords = get_area_coordinates(article.area)
        if not coords:
            continue

        lat, lng = coords
        news_locations.append({
            "article_id": article.id,
            "source": article.source,
            "area": article.area,
            "severity_score": article.severity_score,
            "lat": lat,
            "lng": lng,
        })

    result["news_locations"] = news_locations
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
