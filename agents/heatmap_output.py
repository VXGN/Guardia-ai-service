from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List
import json
import uuid


@dataclass
class HeatmapCell:
    grid_id: str
    latitude_center: float
    longitude_center: float
    incident_count: int
    risk_score: float
    risk_level: str


@dataclass
class HeatmapCluster:
    id: str
    center_lat_blurred: float
    center_lng_blurred: float
    radius_meters: int
    intensity: str
    incident_count: int
    dominant_type: str
    time_slot: str
    valid_from: str
    valid_until: str


def determine_intensity(incident_count: int) -> str:
    if incident_count >= 10:
        return "critical"
    if incident_count >= 6:
        return "high"
    if incident_count >= 3:
        return "medium"
    return "low"


def determine_time_slot(hour: int = None) -> str:
    if hour is None:
        hour = datetime.utcnow().hour
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def blur_coordinate(value: float, precision: int = 3) -> float:
    return round(value, precision)


def cells_to_json(cells: list) -> List[dict]:
    output = []
    for cell in cells:
        output.append({
            "grid_id": cell.grid_id,
            "latitude_center": cell.latitude_center,
            "longitude_center": cell.longitude_center,
            "incident_count": cell.incident_count,
            "risk_score": cell.risk_score,
            "risk_level": cell.risk_level,
        })
    return output


def clusters_to_heatmap(clusters: list, valid_days: int = 7) -> List[HeatmapCluster]:
    now = datetime.utcnow()
    valid_until = now + timedelta(days=valid_days)
    output = []
    for cluster in clusters:
        output.append(HeatmapCluster(
            id=str(uuid.uuid4()),
            center_lat_blurred=blur_coordinate(cluster.center_lat),
            center_lng_blurred=blur_coordinate(cluster.center_lng),
            radius_meters=cluster.radius_meters,
            intensity=determine_intensity(cluster.incident_count),
            incident_count=cluster.incident_count,
            dominant_type=cluster.dominant_category,
            time_slot=determine_time_slot(),
            valid_from=now.isoformat(),
            valid_until=valid_until.isoformat(),
        ))
    return output


def generate_response(cells: list, clusters: list) -> dict:
    heatmap_clusters = clusters_to_heatmap(clusters)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_cells": len(cells),
        "total_clusters": len(clusters),
        "grid_cells": cells_to_json(cells),
        "heatmap_clusters": [asdict(h) for h in heatmap_clusters],
    }


def run(cells: list, clusters: list) -> dict:
    return generate_response(cells, clusters)


def to_json_string(cells: list, clusters: list, indent: int = 2) -> str:
    return json.dumps(generate_response(cells, clusters), indent=indent)
