"""Weather service — current conditions from Open-Meteo."""

import httpx

# WMO Weather interpretation codes → human-readable strings
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def get_historical_weather(lat: float, lon: float, date_str: str) -> dict | None:
    """Fetch historical daily weather from Open-Meteo Archive API.

    Args:
        lat, lon: Coordinates.
        date_str: ISO date string 'YYYY-MM-DD'.
    """
    try:
        resp = httpx.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": date_str,
                "end_date": date_str,
                "daily": "temperature_2m_mean,weather_code,wind_speed_10m_max",
                "timezone": "auto",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})
        if not daily.get("time"):
            return None
        code = daily.get("weather_code", [None])[0]
        return {
            "temp_celsius": daily.get("temperature_2m_mean", [None])[0],
            "conditions": WMO_CODES.get(code, f"Code {code}") if code is not None else None,
            "weather_code": str(code) if code is not None else None,
            "relative_humidity": None,
            "wind_speed_kph": daily.get("wind_speed_10m_max", [None])[0],
            "wind_bearing": None,
            "pressure_mb": None,
        }
    except Exception:
        return None


def get_weather(lat: float, lon: float) -> dict | None:
    """Fetch current weather for coordinates from Open-Meteo."""
    try:
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": ",".join([
                    "temperature_2m",
                    "relative_humidity_2m",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "surface_pressure",
                ]),
                "timezone": "auto",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        current = data.get("current", {})
        code = current.get("weather_code")
        return {
            "temp_celsius": current.get("temperature_2m"),
            "conditions": WMO_CODES.get(code, f"Code {code}") if code is not None else None,
            "weather_code": str(code) if code is not None else None,
            "relative_humidity": current.get("relative_humidity_2m"),
            "wind_speed_kph": current.get("wind_speed_10m"),
            "wind_bearing": current.get("wind_direction_10m"),
            "pressure_mb": current.get("surface_pressure"),
        }
    except Exception:
        return None
