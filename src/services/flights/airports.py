"""Shared airport utilities — OpenFlights database lookup and distance calculation."""

import csv
import logging
import math
from io import StringIO

import httpx

log = logging.getLogger(__name__)

AIRPORTS_URL = "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"

_airports_cache = None


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return int(R * 2 * math.asin(math.sqrt(a)))


def load_airports():
    """Download and parse OpenFlights airport database."""
    global _airports_cache
    if _airports_cache is not None:
        return _airports_cache

    log.info("Downloading airport database...")
    resp = httpx.get(AIRPORTS_URL, timeout=30)
    resp.raise_for_status()

    airports = {}
    reader = csv.reader(StringIO(resp.text))
    for row in reader:
        if len(row) >= 8:
            try:
                iata = row[4] if row[4] != '\\N' else None
                icao = row[5] if row[5] != '\\N' else None
                if iata:
                    airports[iata] = {
                        'name': row[1],
                        'city': row[2],
                        'country': row[3],
                        'iata': iata,
                        'icao': icao,
                        'lat': float(row[6]),
                        'lon': float(row[7]),
                    }
                if icao and icao not in airports:
                    airports[icao] = {
                        'name': row[1],
                        'city': row[2],
                        'country': row[3],
                        'iata': iata,
                        'icao': icao,
                        'lat': float(row[6]),
                        'lon': float(row[7]),
                    }
            except (ValueError, IndexError):
                continue

    log.info("Loaded %d airports", len(airports))
    _airports_cache = airports
    return airports


def lookup_airport(iata):
    """Look up airport by IATA code. Returns dict or None."""
    airports = load_airports()
    return airports.get(iata)
