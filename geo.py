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
    url = f"{PHOTON_BASE_URL}?q={urllib.parse.quote(query)}&limit={int(limit)}&lang=en"
    try:
        data = http_get_json(url, timeout=10)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return []
    features = data.get("features") or []
    out: list[Dict[str, Any]] = []
    for feat in features[:limit]:
        try:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = (geom.get("coordinates") or [None, None])
            if not coords or len(coords) < 2:
                continue
            coord_lon = coords[0]
            coord_lat = coords[1]
            if coord_lon is None or coord_lat is None:
                continue
            lon = float(coord_lon)
            lat = float(coord_lat)
            name = props.get("name") or ""
            city = props.get("city") or ""
            state = props.get("state") or props.get("region") or ""
            country = props.get("country") or ""
            parts = [p for p in (name, city, state, country) if isinstance(p, str) and p.strip()]
            label = ", ".join(dict.fromkeys(parts))[:140]
            if not label:
                continue
            out.append({"label": label, "lat": lat, "lon": lon})
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
