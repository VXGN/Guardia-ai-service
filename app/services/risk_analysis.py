import math
from datetime import datetime
from collections import Counter
from typing import Protocol

from app.models.tables import RoadSegment
from app.models.enums import TimeSlot
from app.repositories.repos import RiskScoreRepository


class IncidentLike(Protocol):
    latitude: float
    longitude: float
    incident_type: object
    incident_at: datetime
    severity_score: int | None


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371000
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_time_slot(dt: datetime) -> TimeSlot:
    h = dt.hour
    if 6 <= h < 12:
        return TimeSlot.morning
    if 12 <= h < 17:
        return TimeSlot.afternoon
    if 17 <= h < 21:
        return TimeSlot.evening
    return TimeSlot.night


async def compute_risk_scores(
    segments: list[RoadSegment],
    reports: list[IncidentLike],
    risk_repo: RiskScoreRepository,
):
    current_slot = _get_time_slot(datetime.utcnow())

    for segment in segments:
        seg_lat = (float(segment.start_lat) + float(segment.end_lat)) / 2
        seg_lng = (float(segment.start_lng) + float(segment.end_lng)) / 2

        nearby = [
            r for r in reports
            if _haversine(float(r.latitude), float(r.longitude), seg_lat, seg_lng) < 500
        ]

        slots: dict[TimeSlot, list[IncidentLike]] = {}
        for r in nearby:
            slot = _get_time_slot(r.incident_at)
            slots.setdefault(slot, []).append(r)

        if not slots:
            await risk_repo.upsert(segment.id, current_slot, 0.0, 0, None)
            continue

        for slot, slot_reports in slots.items():
            count = len(slot_reports)
            severity_sum = sum(r.severity_score or 5 for r in slot_reports)

            base_score = min(count * 10 + severity_sum, 100)
            if not segment.has_street_light:
                base_score = min(base_score * 1.2, 100)
            if not segment.is_main_road:
                base_score = min(base_score * 1.1, 100)
            if segment.near_security_post:
                base_score *= 0.8

            types = [r.incident_type for r in slot_reports]
            dominant = Counter(types).most_common(1)[0][0] if types else None

            await risk_repo.upsert(segment.id, slot, round(base_score, 2), count, dominant)

    await risk_repo.db.commit()


async def analyze_path_risk(
    segments: list[RoadSegment],
    risk_repo: RiskScoreRepository,
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> dict:
    now = datetime.utcnow()
    current_slot = _get_time_slot(now)

    path_segments = []
    for seg in segments:
        seg_lat = (float(seg.start_lat) + float(seg.end_lat)) / 2
        seg_lng = (float(seg.start_lng) + float(seg.end_lng)) / 2
        d_start = _haversine(start_lat, start_lng, seg_lat, seg_lng)
        d_end = _haversine(end_lat, end_lng, seg_lat, seg_lng)
        if d_start < 2000 or d_end < 2000:
            path_segments.append(seg)

    result_segments = []
    total_score = 0.0

    for seg in path_segments:
        scores = await risk_repo.get_by_segment(seg.id)
        slot_score = next((s for s in scores if s.time_slot == current_slot), None)
        score_val = float(slot_score.risk_score) if slot_score else 0.0
        total_score += score_val

        factors = []
        if not seg.has_street_light:
            factors.append("no_street_light")
        if not seg.is_main_road:
            factors.append("minor_road")
        if slot_score and slot_score.dominant_incident_type:
            factors.append(f"dominant:{slot_score.dominant_incident_type.value}")

        seg_lat = (float(seg.start_lat) + float(seg.end_lat)) / 2
        seg_lng = (float(seg.start_lng) + float(seg.end_lng)) / 2
        result_segments.append({
            "segment_id": seg.id,
            "risk_score": score_val,
            "risk_factors": factors,
            "lat": seg_lat,
            "lng": seg_lng,
        })

    overall = total_score / len(path_segments) if path_segments else 0
    level = "low"
    if overall >= 70:
        level = "critical"
    elif overall >= 50:
        level = "high"
    elif overall >= 30:
        level = "medium"

    recommendations = []
    if level in ("high", "critical"):
        recommendations.append("Consider using a main road with better lighting")
        recommendations.append("Share your journey with a trusted contact")
    if current_slot == TimeSlot.night:
        recommendations.append("Extra caution recommended during nighttime travel")

    return {
        "overall_risk_score": round(overall, 2),
        "risk_level": level,
        "segments": result_segments,
        "recommendations": recommendations,
        "analyzed_at": now.isoformat(),
    }
