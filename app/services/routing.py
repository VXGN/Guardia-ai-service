import math
from datetime import datetime

import networkx as nx

from app.models.tables import RoadSegment
from app.models.enums import TimeSlot
from app.repositories.repos import RiskScoreRepository


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


async def build_graph(
    segments: list[RoadSegment],
    risk_repo: RiskScoreRepository,
) -> nx.Graph:
    G = nx.Graph()
    current_slot = _get_time_slot(datetime.utcnow())

    for seg in segments:
        s = (float(seg.start_lat), float(seg.start_lng))
        e = (float(seg.end_lat), float(seg.end_lng))
        dist = _haversine(s[0], s[1], e[0], e[1])

        scores = await risk_repo.get_by_segment(seg.id)
        slot_score = next((sc for sc in scores if sc.time_slot == current_slot), None)
        risk = float(slot_score.risk_score) if slot_score else 0.0

        safety_factor = 1.0
        if seg.has_street_light:
            safety_factor *= 0.8
        if seg.is_main_road:
            safety_factor *= 0.7
        if seg.near_security_post:
            safety_factor *= 0.6

        weight = dist * (1 + (risk / 100)) * safety_factor

        G.add_edge(s, e, weight=weight, distance=dist, risk=risk, segment_id=seg.id)

    return G


def _find_nearest_node(G: nx.Graph, lat: float, lng: float):
    best = None
    best_dist = float("inf")
    for node in G.nodes:
        d = _haversine(lat, lng, node[0], node[1])
        if d < best_dist:
            best_dist = d
            best = node
    return best


async def calculate_safe_route(
    segments: list[RoadSegment],
    risk_repo: RiskScoreRepository,
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> dict:
    G = await build_graph(segments, risk_repo)

    if len(G.nodes) == 0:
        return {
            "route": [
                {"lat": start_lat, "lng": start_lng},
                {"lat": end_lat, "lng": end_lng},
            ],
            "total_distance_meters": _haversine(start_lat, start_lng, end_lat, end_lng),
            "total_risk_score": 0,
            "estimated_duration_seconds": _haversine(start_lat, start_lng, end_lat, end_lng) / 1.4,
            "avoided_risk_zones": 0,
        }

    source = _find_nearest_node(G, start_lat, start_lng)
    target = _find_nearest_node(G, end_lat, end_lng)

    try:
        path = nx.shortest_path(G, source, target, weight="weight")
    except nx.NetworkXNoPath:
        return {
            "route": [
                {"lat": start_lat, "lng": start_lng},
                {"lat": end_lat, "lng": end_lng},
            ],
            "total_distance_meters": _haversine(start_lat, start_lng, end_lat, end_lng),
            "total_risk_score": 0,
            "estimated_duration_seconds": _haversine(start_lat, start_lng, end_lat, end_lng) / 1.4,
            "avoided_risk_zones": 0,
        }

    route_points = [{"lat": start_lat, "lng": start_lng}]
    total_dist = 0.0
    total_risk = 0.0
    avoided = 0

    for i in range(len(path) - 1):
        edge = G.edges[path[i], path[i + 1]]
        total_dist += edge["distance"]
        total_risk += edge["risk"]
        if edge["risk"] >= 50:
            avoided += 1
        route_points.append({"lat": path[i + 1][0], "lng": path[i + 1][1]})

    route_points.append({"lat": end_lat, "lng": end_lng})
    avg_risk = total_risk / max(len(path) - 1, 1)
    duration = total_dist / 1.4

    return {
        "route": route_points,
        "total_distance_meters": round(total_dist, 2),
        "total_risk_score": round(avg_risk, 2),
        "estimated_duration_seconds": round(duration, 2),
        "avoided_risk_zones": avoided,
    }
