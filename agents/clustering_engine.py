from dataclasses import dataclass
from typing import List
from collections import Counter
import numpy as np
from sklearn.cluster import DBSCAN


@dataclass
class Cluster:
    cluster_id: int
    center_lat: float
    center_lng: float
    radius_meters: int
    incident_count: int
    dominant_category: str
    avg_severity: float
    points: list


def to_feature_matrix(points: list) -> np.ndarray:
    if not points:
        return np.array([])
    return np.array([[p.latitude, p.longitude] for p in points])


def km_to_degrees(km: float) -> float:
    return km / 111.0


def run(points: list, eps_km: float = 0.3, min_samples: int = 3) -> List[Cluster]:
    if len(points) < min_samples:
        return []

    coords = to_feature_matrix(points)
    eps_deg = km_to_degrees(eps_km)

    db = DBSCAN(eps=eps_deg, min_samples=min_samples, metric="euclidean")
    labels = db.fit_predict(coords)

    clusters = []
    for label in set(labels):
        if label == -1:
            continue

        mask = labels == label
        cluster_points = [p for p, m in zip(points, mask) if m]
        cluster_coords = coords[mask]

        center_lat = float(np.mean(cluster_coords[:, 0]))
        center_lng = float(np.mean(cluster_coords[:, 1]))

        lat_range = cluster_coords[:, 0].max() - cluster_coords[:, 0].min()
        lng_range = cluster_coords[:, 1].max() - cluster_coords[:, 1].min()
        radius_meters = int(max(lat_range, lng_range) * 111000 / 2) or 100

        categories = [p.category for p in cluster_points]
        dominant = Counter(categories).most_common(1)[0][0] if categories else "other"

        severities = [p.severity for p in cluster_points]
        avg_severity = sum(severities) / len(severities) if severities else 0

        clusters.append(Cluster(
            cluster_id=int(label),
            center_lat=round(center_lat, 5),
            center_lng=round(center_lng, 5),
            radius_meters=radius_meters,
            incident_count=len(cluster_points),
            dominant_category=dominant,
            avg_severity=round(avg_severity, 2),
            points=cluster_points,
        ))

    return sorted(clusters, key=lambda c: c.incident_count, reverse=True)
