import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.models.enums import HeatmapIntensity, IncidentType, TimeSlot
from app.models.tables import HeatmapCluster
from app.services.area_coordinates import get_area_coordinates


@dataclass
class AreaRiskScore:
    area: str
    total_articles: int
    avg_severity: float
    dominant_crime: str | None
    score: float
    period_start: datetime
    period_end: datetime
    calculated_at: datetime


def _score_to_intensity(score: float) -> HeatmapIntensity:
    if score >= 80:
        return HeatmapIntensity.critical
    if score >= 60:
        return HeatmapIntensity.high
    if score >= 40:
        return HeatmapIntensity.medium
    return HeatmapIntensity.low


def _now_slot(now: datetime) -> TimeSlot:
    h = now.hour
    if 6 <= h < 12:
        return TimeSlot.morning
    if 12 <= h < 17:
        return TimeSlot.afternoon
    if 17 <= h < 21:
        return TimeSlot.evening
    return TimeSlot.night


def build_area_risk_scores(news_articles: list, window_days: int = 30) -> list[AreaRiskScore]:
    now = datetime.utcnow()
    period_start = now - timedelta(days=window_days)

    grouped: dict[str, list] = defaultdict(list)
    for article in news_articles:
        if not article.area:
            continue
        if get_area_coordinates(article.area) is None:
            continue
        grouped[article.area].append(article)

    results: list[AreaRiskScore] = []
    for area, articles in grouped.items():
        severities = [float(a.severity_score or 0) for a in articles]
        total = len(articles)
        avg_sev = (sum(severities) / total) if total else 0.0
        crimes = [a.crime_type for a in articles if a.crime_type]
        dominant = Counter(crimes).most_common(1)[0][0] if crimes else None

        # Composite score tuned for area-level monitoring.
        severity_component = min(70.0, avg_sev * 7.0)
        volume_component = min(30.0, math.log1p(total) * 10.0)
        score = round(min(100.0, severity_component + volume_component), 2)

        results.append(
            AreaRiskScore(
                area=area,
                total_articles=total,
                avg_severity=round(avg_sev, 2),
                dominant_crime=dominant,
                score=score,
                period_start=period_start,
                period_end=now,
                calculated_at=now,
            )
        )

    results.sort(key=lambda x: (x.score, x.total_articles), reverse=True)
    return results


def area_risk_scores_to_rows(scores: list[AreaRiskScore]) -> list[dict]:
    rows: list[dict] = []
    for score in scores:
        rows.append(
            {
                "area": score.area,
                "total_articles": score.total_articles,
                "avg_severity": Decimal(str(score.avg_severity)),
                "dominant_crime": score.dominant_crime,
                "score": Decimal(str(score.score)),
                "period_start": score.period_start,
                "period_end": score.period_end,
                "calculated_at": score.calculated_at,
            }
        )
    return rows


def area_risk_scores_to_heatmap_clusters(scores: list[AreaRiskScore]) -> list[HeatmapCluster]:
    now = datetime.utcnow()
    slot = _now_slot(now)
    clusters: list[HeatmapCluster] = []

    for score in scores:
        coords = get_area_coordinates(score.area)
        if not coords:
            continue

        lat, lng = coords
        radius = max(800, min(6000, 900 + score.total_articles * 220))

        clusters.append(
            HeatmapCluster(
                center_lat_blurred=Decimal(str(round(lat, 5))),
                center_lng_blurred=Decimal(str(round(lng, 5))),
                radius_meters=radius,
                intensity=_score_to_intensity(score.score),
                incident_count=score.total_articles,
                dominant_type=IncidentType.other,
                time_slot=slot,
                valid_from=now,
                valid_until=now + timedelta(days=7),
            )
        )

    return clusters
