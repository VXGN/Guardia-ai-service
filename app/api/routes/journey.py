from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.schemas.journey_schemas import JourneyStartIn, JourneyUpdateIn, JourneyStopIn, JourneyOut
from app.repositories.repos import JourneyRepository
from app.services.journey import start_journey, update_journey, stop_journey

router = APIRouter(prefix="/journey", tags=["journey"])


@router.post("/start", response_model=JourneyOut)
async def journey_start(
    body: JourneyStartIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    repo = JourneyRepository(db)
    return await start_journey(
        repo, body.user_id,
        body.origin_lat, body.origin_lng,
        body.destination_lat, body.destination_lng,
    )


@router.post("/update", response_model=JourneyOut)
async def journey_update(
    body: JourneyUpdateIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    repo = JourneyRepository(db)
    result = await update_journey(repo, body.journey_id, body.latitude, body.longitude)
    if not result:
        raise HTTPException(404, "Journey not found")
    return result


@router.post("/stop", response_model=JourneyOut)
async def journey_stop(
    body: JourneyStopIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(verify_firebase_token),
):
    repo = JourneyRepository(db)
    result = await stop_journey(repo, body.journey_id, body.safe_arrival)
    if not result:
        raise HTTPException(404, "Journey not found")
    return result
