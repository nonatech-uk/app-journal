"""Context endpoint — aggregates current location, weather, music, and media."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from config.settings import settings
from src.api.deps import get_current_user
from src.services.location import get_current_location, reverse_geocode
from src.services.scrobbles import get_recent_scrobbles
from src.services.tautulli import get_recent_watches
from src.services.weather import get_weather

router = APIRouter()


@router.get("/context/now")
def get_context_now(_user=Depends(get_current_user)):
    """Fetch current context: location, weather, recent music, recent media."""
    result = {
        "location": None,
        "weather": None,
        "scrobbles": [],
        "tautulli_watches": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Location
    loc = get_current_location(settings)
    if loc:
        geo = reverse_geocode(loc["latitude"], loc["longitude"])
        loc.update(geo)
        result["location"] = loc

        # Weather (requires location)
        weather = get_weather(loc["latitude"], loc["longitude"])
        if weather:
            result["weather"] = weather

    # Recent scrobbles
    result["scrobbles"] = get_recent_scrobbles(settings, minutes=60, limit=10)

    # Recent Tautulli watches
    result["tautulli_watches"] = get_recent_watches(settings, limit=5)

    return result
