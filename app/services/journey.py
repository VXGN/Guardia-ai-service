from datetime import datetime
from decimal import Decimal

from app.models.enums import JourneyStatus
from app.repositories.repos import JourneyRepository


async def start_journey(repo: JourneyRepository, user_id: str, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
    return await repo.create(
        user_id=user_id,
        started_at=datetime.utcnow(),
        origin_lat=Decimal(str(origin_lat)),
        origin_lng=Decimal(str(origin_lng)),
        destination_lat=Decimal(str(dest_lat)),
        destination_lng=Decimal(str(dest_lng)),
    )


async def update_journey(repo: JourneyRepository, journey_id: str, lat: float, lng: float):
    journey = await repo.get_by_id(journey_id)
    if not journey:
        return None
    await repo.add_location_log(journey_id, lat, lng)
    return journey


async def stop_journey(repo: JourneyRepository, journey_id: str, safe_arrival: bool = False):
    status = JourneyStatus.completed if safe_arrival else JourneyStatus.cancelled
    return await repo.update_status(
        journey_id,
        status,
        ended_at=datetime.utcnow(),
        safe_arrival_confirmed=safe_arrival,
    )
