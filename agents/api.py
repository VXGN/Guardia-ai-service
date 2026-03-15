from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from agents import run_pipeline, run_with_existing_data, PipelineConfig
from agents.dataset_builder import IncidentPoint
from agents.heatmap_output import to_json_string


router = APIRouter(prefix="/agents", tags=["agents"])


class UserReport(BaseModel):
    latitude: float
    longitude: float
    incident_at: str
    incident_type: str
    severity_score: Optional[int] = None


class GenerateRequest(BaseModel):
    user_reports: Optional[List[UserReport]] = None
    max_articles: int = 100
    max_pages: int = 5
    sources: Optional[List[str]] = None
    filter_days: int = 90
    eps_km: float = 0.3
    min_cluster_samples: int = 3
    grid_cell_km: float = 1.0


class HeatmapClusterOut(BaseModel):
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


class GridCellOut(BaseModel):
    grid_id: str
    latitude_center: float
    longitude_center: float
    incident_count: int
    risk_score: float
    risk_level: str


class GenerateResponse(BaseModel):
    generated_at: str
    total_cells: int
    total_clusters: int
    grid_cells: List[GridCellOut]
    heatmap_clusters: List[HeatmapClusterOut]


@router.post("/generate", response_model=GenerateResponse)
async def generate_heatmap(request: GenerateRequest):
    config = PipelineConfig(
        max_articles=request.max_articles,
        max_pages=request.max_pages,
        sources=request.sources or ["detik", "insidelombok", "postlombok"],
        filter_days=request.filter_days,
        eps_km=request.eps_km,
        min_cluster_samples=request.min_cluster_samples,
        grid_cell_km=request.grid_cell_km,
    )

    user_reports = None
    if request.user_reports:
        user_reports = [r.model_dump() for r in request.user_reports]

    result = await run_pipeline(user_reports=user_reports, config=config)

    return result


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "guardia-ai-agents"}
