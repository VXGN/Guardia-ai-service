from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
import math


@dataclass
class GridCell:
    grid_id: str
    latitude_center: float
    longitude_center: float
    incident_count: int
    cluster_density: float
    avg_severity: float
    risk_score: float
    risk_level: str


NTB_BOUNDS = {
    "min_lat": -9.0,
    "max_lat": -8.0,
    "min_lng": 115.5,
    "max_lng": 119.5,
}


def create_grid(cell_size_km: float = 1.0, bounds: dict = None) -> List[tuple]:
    if bounds is None:
        bounds = NTB_BOUNDS

    cell_size_deg = cell_size_km / 111.0
    cells = []

    lat = bounds["min_lat"]
    while lat < bounds["max_lat"]:
        lng = bounds["min_lng"]
        while lng < bounds["max_lng"]:
            center_lat = lat + cell_size_deg / 2
            center_lng = lng + cell_size_deg / 2
            cells.append((center_lat, center_lng))
            lng += cell_size_deg
        lat += cell_size_deg

    return cells


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371000
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_recency_weight(timestamp: datetime, max_days: int = 90) -> float:
    if timestamp is None:
        return 0.5
    days_ago = (datetime.utcnow() - timestamp).days
    if days_ago > max_days:
        return 0.1
    return 1.0 - (days_ago / max_days) * 0.9


def compute_cell_risk(cell_center: tuple, points: list, clusters: list, cell_radius_meters: float = 500) -> GridCell:
    center_lat, center_lng = cell_center

    nearby_points = []
    for p in points:
        dist = haversine_distance(center_lat, center_lng, p.latitude, p.longitude)
        if dist <= cell_radius_meters:
            nearby_points.append(p)

    incident_count = len(nearby_points)

    cluster_density = 0.0
    for cluster in clusters:
        dist = haversine_distance(center_lat, center_lng, cluster.center_lat, cluster.center_lng)
        if dist <= cluster.radius_meters + cell_radius_meters:
            cluster_density += cluster.incident_count / max(dist + 1, 1)

    if incident_count == 0 and cluster_density == 0:
        return None

    severity_sum = sum(p.severity for p in nearby_points)
    avg_severity = severity_sum / incident_count if incident_count > 0 else 0

    recency_weights = [calculate_recency_weight(p.timestamp) for p in nearby_points]
    avg_recency = sum(recency_weights) / len(recency_weights) if recency_weights else 0

    base_score = min(incident_count * 5, 40)
    severity_score = min(avg_severity * 3, 30)
    cluster_score = min(cluster_density * 2, 20)
    recency_score = avg_recency * 10

    risk_score = min(base_score + severity_score + cluster_score + recency_score, 100)
    risk_score = round(risk_score, 2)

    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    grid_id = f"{round(center_lat, 3)}_{round(center_lng, 3)}"

    return GridCell(
        grid_id=grid_id,
        latitude_center=round(center_lat, 5),
        longitude_center=round(center_lng, 5),
        incident_count=incident_count,
        cluster_density=round(cluster_density, 2),
        avg_severity=round(avg_severity, 2),
        risk_score=risk_score,
        risk_level=risk_level,
    )


def run(points: list, clusters: list, cell_size_km: float = 1.0, bounds: dict = None) -> List[GridCell]:
    grid_centers = create_grid(cell_size_km, bounds)
    cell_radius = cell_size_km * 1000 / 2

    cells = []
    for center in grid_centers:
        cell = compute_cell_risk(center, points, clusters, cell_radius)
        if cell is not None:
            cells.append(cell)

    return sorted(cells, key=lambda c: c.risk_score, reverse=True)
