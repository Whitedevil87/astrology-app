import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from config import PHOTON_BASE_URL, TIMEAPI_BASE_URL


def http_get_json(url: str, timeout: int = 12) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CelestialArc/1.0 (Flask; local educational app)",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def photon_search(q: str, limit: int = 7) -> list[Dict[str, Any]]:
    query = (q or "").strip()
    if not query:
        return []
    # Switching to Open-Meteo Geocoding API for much faster response times
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(query)}&count={int(limit)}&language=en&format=json"
    try:
        data = http_get_json(url, timeout=5)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return []
    
    results = data.get("results") or []
    out: list[Dict[str, Any]] = []
    for res in results[:limit]:
        try:
            lat = res.get("latitude")
            lon = res.get("longitude")
            if lat is None or lon is None:
                continue
            
            name = res.get("name") or ""
            state = res.get("admin1") or ""
            country = res.get("country") or ""
            
            parts = [p for p in (name, state, country) if isinstance(p, str) and p.strip()]
            label = ", ".join(dict.fromkeys(parts))[:140]
            if not label:
                continue
            out.append({"label": label, "lat": float(lat), "lon": float(lon)})
        except (TypeError, ValueError):
            continue
    return out


def timeapi_timezone_name(lat: float, lon: float) -> Optional[str]:
    url = (
        f"{TIMEAPI_BASE_URL}/timezone/coordinate"
        f"?latitude={urllib.parse.quote(str(lat))}&longitude={urllib.parse.quote(str(lon))}"
    )
    try:
        data = http_get_json(url, timeout=10)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    tz = data.get("timeZone") or data.get("timezone") or data.get("time_zone")
    return str(tz).strip() if tz else None
