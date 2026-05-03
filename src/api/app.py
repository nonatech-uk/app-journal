"""Journal API — FastAPI application."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.api.deps import close_pool, init_pool
from src.api.routers import activities, auth, calendar, context, daily_summary, enrichment, entries, events, flights, gps, immich, journals, map, media, memoirs, people, places, scrobbles, search, stats, tags, transport, trips, watches

from mees_shared.usage_tracker import init_usage_tracker, shutdown_usage_tracker, track_usage_middleware, usage_pageview_router
from mees_shared.dashboard import register_with_dashboard
from mees_shared.spa import mount_spa

STATIC_DIR = Path(_project_root) / "static"

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    init_usage_tracker("journal", settings.usage_dsn)
    task = asyncio.create_task(register_with_dashboard(
        label="Journal",
        href="https://journal.mees.st",
        icon="\u25EB",
        sort_order=1,
        registry_key=settings.dash_registry_key,
    ))
    yield
    task.cancel()
    shutdown_usage_tracker()
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

app.middleware("http")(track_usage_middleware)

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
app.include_router(gps.router, prefix="/api/v1", tags=["gps"])
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
app.include_router(events.router, prefix="/api/v1", tags=["events"])
app.include_router(memoirs.router, prefix="/api/v1", tags=["memoirs"])
app.include_router(transport.router, prefix="/api/v1", tags=["transport"])
app.include_router(usage_pageview_router, prefix="/api/v1")

# SPA serving + /health endpoint
mount_spa(app, STATIC_DIR)
