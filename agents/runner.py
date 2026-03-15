import asyncio
from dataclasses import dataclass
from typing import List

from agents import news_scraper
from agents import dataset_builder
from agents import clustering_engine
from agents import risk_scorer
from agents import heatmap_output


@dataclass
class PipelineConfig:
    max_articles: int = 100
    max_pages: int = 5
    sources: list = None
    filter_days: int = 90
    eps_km: float = 0.3
    min_cluster_samples: int = 3
    grid_cell_km: float = 1.0
    grid_bounds: dict = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = ["detik", "insidelombok", "postlombok"]


async def run_pipeline(user_reports: list = None, config: PipelineConfig = None) -> dict:
    if config is None:
        config = PipelineConfig()

    scrape_config = news_scraper.ScrapeConfig(
        max_articles=config.max_articles,
        max_pages=config.max_pages,
        sources=config.sources,
    )
    articles = await news_scraper.run(scrape_config)

    points = dataset_builder.run(
        news_articles=articles,
        user_reports=user_reports,
        filter_days=config.filter_days,
    )

    clusters = clustering_engine.run(
        points=points,
        eps_km=config.eps_km,
        min_samples=config.min_cluster_samples,
    )

    cells = risk_scorer.run(
        points=points,
        clusters=clusters,
        cell_size_km=config.grid_cell_km,
        bounds=config.grid_bounds,
    )

    output = heatmap_output.run(cells=cells, clusters=clusters)

    return output


async def run_with_existing_data(points: list, config: PipelineConfig = None) -> dict:
    if config is None:
        config = PipelineConfig()

    clusters = clustering_engine.run(
        points=points,
        eps_km=config.eps_km,
        min_samples=config.min_cluster_samples,
    )

    cells = risk_scorer.run(
        points=points,
        clusters=clusters,
        cell_size_km=config.grid_cell_km,
        bounds=config.grid_bounds,
    )

    output = heatmap_output.run(cells=cells, clusters=clusters)

    return output


def run_sync(user_reports: list = None, config: PipelineConfig = None) -> dict:
    return asyncio.run(run_pipeline(user_reports, config))


if __name__ == "__main__":
    result = run_sync()
    print(heatmap_output.to_json_string(result["grid_cells"], result["heatmap_clusters"]))
