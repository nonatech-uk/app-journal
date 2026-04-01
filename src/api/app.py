"""Journal API — FastAPI application."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from src.api.deps import close_pool, init_pool
from src.api.routers import activities, auth, calendar, context, daily_summary, enrichment, entries, flights, immich, journals, map, media, people, places, scrobbles, search, stats, tags, trips, watches

STATIC_DIR = Path(_project_root) / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


app = FastAPI(
    title="Journal API",
    version="0.1.0",
    description="Personal journal API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(entries.router, prefix="/api/v1", tags=["entries"])
app.include_router(journals.router, prefix="/api/v1", tags=["journals"])
app.include_router(tags.router, prefix="/api/v1", tags=["tags"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(calendar.router, prefix="/api/v1", tags=["calendar"])
app.include_router(map.router, prefix="/api/v1", tags=["map"])
app.include_router(media.router, prefix="/api/v1", tags=["media"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(enrichment.router, prefix="/api/v1", tags=["enrichment"])
app.include_router(context.router, prefix="/api/v1", tags=["context"])
app.include_router(flights.router, prefix="/api/v1", tags=["flights"])
app.include_router(activities.router, prefix="/api/v1", tags=["activities"])
app.include_router(scrobbles.router, prefix="/api/v1", tags=["scrobbles"])
app.include_router(people.router, prefix="/api/v1", tags=["people"])
app.include_router(trips.router, prefix="/api/v1", tags=["trips"])
app.include_router(watches.router, prefix="/api/v1", tags=["watches"])
app.include_router(immich.router, prefix="/api/v1", tags=["immich"])
app.include_router(daily_summary.router, prefix="/api/v1", tags=["daily_summary"])
app.include_router(places.router, prefix="/api/v1", tags=["places"])


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve React SPA
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file_path = STATIC_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
