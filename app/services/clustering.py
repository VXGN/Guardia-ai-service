import math
from datetime import datetime, timedelta
from decimal import Decimal
from collections import Counter

import numpy as np
from sklearn.cluster import DBSCAN

from app.models.tables import IncidentReport, HeatmapCluster
from app.models.enums import HeatmapIntensity, TimeSlot


def _get_time_slot(dt: datetime) -> TimeSlot:
    h = dt.hour
    if 6 <= h < 12:
        return TimeSlot.morning
    if 12 <= h < 17:
        return TimeSlot.afternoon
    if 17 <= h < 21:
        return TimeSlot.evening
    return TimeSlot.night


def _intensity(count: int) -> HeatmapIntensity:
    if count >= 10:
        return HeatmapIntensity.critical
    if count >= 6:
        return HeatmapIntensity.high
    if count >= 3:
        return HeatmapIntensity.medium
    return HeatmapIntensity.low


async def cluster_reports(
    reports: list[IncidentReport],
    eps_km: float = 0.3,
    min_samples: int = 3,
) -> list[HeatmapCluster]:
    if len(reports) < min_samples:
        return []

    coords = np.array([[float(r.latitude), float(r.longitude)] for r in reports])
    eps_deg = eps_km / 111.0
    db = DBSCAN(eps=eps_deg, min_samples=min_samples, metric="euclidean")
    labels = db.fit_predict(coords)

    clusters: list[HeatmapCluster] = []
    now = datetime.utcnow()

    for label in set(labels):
        if label == -1:
            continue
        mask = labels == label
        cluster_reports_list = [r for r, m in zip(reports, mask) if m]
        cluster_coords = coords[mask]

        center_lat = round(float(cluster_coords[:, 0].mean()), 5)
        center_lng = round(float(cluster_coords[:, 1].mean()), 5)

        lat_range = cluster_coords[:, 0].max() - cluster_coords[:, 0].min()
        lng_range = cluster_coords[:, 1].max() - cluster_coords[:, 1].min()
        radius = int(max(lat_range, lng_range) * 111000 / 2) or 100

        types = [r.incident_type for r in cluster_reports_list]
        dominant = Counter(types).most_common(1)[0][0] if types else None

        time_slots = [_get_time_slot(r.incident_at) for r in cluster_reports_list]
        dominant_slot = Counter(time_slots).most_common(1)[0][0] if time_slots else None

        clusters.append(HeatmapCluster(
            center_lat_blurred=Decimal(str(center_lat)),
            center_lng_blurred=Decimal(str(center_lng)),
            radius_meters=radius,
            intensity=_intensity(len(cluster_reports_list)),
            incident_count=len(cluster_reports_list),
            dominant_type=dominant,
            time_slot=dominant_slot,
            valid_from=now,
            valid_until=now + timedelta(days=7),
        ))

    return clusters
