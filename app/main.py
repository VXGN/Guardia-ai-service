from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.core.config import get_settings
from app.api.routes import heatmap, analysis, journey, news
from app.services.stream_sync import start_background_sync

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop_event = None
    tasks = []

    if settings.ENABLE_BACKGROUND_SYNC:
        stop_event = asyncio.Event()
        tasks = start_background_sync(stop_event)

    try:
        yield
    finally:
        if stop_event:
            stop_event.set()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

app = FastAPI(
    title="Guardia AI Service",
    version="1.0.0",
    description="AI-focused microservice for risk analysis, clustering, routing, and news processing",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI-focused routes only
app.include_router(heatmap.router)    # Heatmap clustering
app.include_router(analysis.router)   # Risk analysis with DBSCAN
app.include_router(journey.router)    # Journey tracking with risk monitoring
app.include_router(news.router)       # News scraping and crime scoring


@app.get("/health")
async def health():
    return {"status": "ok", "service": "guardia-ai"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0", port=8000, reload=True)