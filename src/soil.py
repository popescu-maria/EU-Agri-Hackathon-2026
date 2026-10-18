import json
import sys
import time
import math
from pathlib import Path

import requests

from src.weather import geocode

URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "cache" / "soil_cache.json"
TIMEOUT = 30
PROPERTIES = ["phh2o", "clay", "sand", "silt", "soc"]
DEPTH_WEIGHTS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
SEARCH_RADII_KM = (2, 5)
SEARCH_BEARINGS = range(0, 360, 45)

TEXTURE_GROUPS = {
    "light": {"sand", "loamy sand", "sandy loam"},
    "medium": {"loam", "silt loam", "silt", "sandy clay loam"},
    "heavy": {"clay loam", "silty clay loam", "sandy clay", "silty clay", "clay"},
}


def _fetch(lat, lon, attempts=3):
    params = {
        "lat": lat,
        "lon": lon,
        "property": PROPERTIES,
        "depth": list(DEPTH_WEIGHTS),
        "value": "mean",
    }
    for i in range(attempts):
        r = requests.get(URL, params=params, timeout=TIMEOUT)
        if r.status_code not in (429, 500, 502, 503, 504):
            break
        time.sleep(3 * 2 ** i)
    if not r.ok:
        raise RuntimeError(f"SoilGrids error {r.status_code}: {r.text[:200]}")
    return r.json()


def _topsoil_means(data):
    means = {}
    for layer in data["properties"]["layers"]:
        factor = layer["unit_measure"]["d_factor"]
        total = weight = 0
        for depth in layer["depths"]:
            value = depth["values"].get("mean")
            if value is None:
                continue
            w = DEPTH_WEIGHTS.get(depth["label"], 1)
            total += value / factor * w
            weight += w
        means[layer["name"]] = total / weight if weight else None
    return means


def usda_class(clay, sand, silt):
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 2 * clay < 30:
        return "loamy sand"
    if (7 <= clay < 20 and sand > 52) or (clay < 7 and silt < 50):
        return "sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty clay loam"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    if clay >= 40:
        return "clay"
    return "loam"


def texture_group(texture_class):
    return next(g for g, classes in TEXTURE_GROUPS.items() if texture_class in classes)


def organic_matter_level(soc_g_kg):
    if soc_g_kg < 10:
        return "low"
    return "medium" if soc_g_kg <= 20 else "high"


def build_profile(means):
    if any(means.get(k) is None for k in PROPERTIES):
        raise ValueError("No soil data at this point (water, urban or unmapped area)")

    total = means["clay"] + means["sand"] + means["silt"]
    clay, sand, silt = (means[k] / total * 100 for k in ("clay", "sand", "silt"))
    texture = usda_class(clay, sand, silt)

    return {
        "ph": round(means["phh2o"], 1),
        "clay_pct": round(clay, 1),
        "sand_pct": round(sand, 1),
        "silt_pct": round(silt, 1),
        "organic_carbon_g_kg": round(means["soc"], 1),
        "texture_class": texture,
        "texture_group": texture_group(texture),
        "organic_matter": organic_matter_level(means["soc"]),
        "source": "soilgrids",
    }

def _offset(lat, lon, km, bearing):
    d = km / 111.0
    b = math.radians(bearing)
    return lat + d * math.cos(b), lon + d * math.sin(b) / math.cos(math.radians(lat))


def _lookup(lat, lon):
    try:
        return build_profile(_topsoil_means(_fetch(lat, lon)))
    except ValueError:
        return None


def _find_profile(lat, lon):
    profile = _lookup(lat, lon)
    if profile:
        return {**profile, "distance_km": 0}

    for km in SEARCH_RADII_KM:
        for bearing in SEARCH_BEARINGS:
            time.sleep(1)
            profile = _lookup(*_offset(lat, lon, km, bearing))
            if profile:
                return {**profile, "distance_km": km}

    raise ValueError("No soil data within 5 km of this point")

def _read_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def get_soil(lat, lon):
    key = f"{lat:.3f},{lon:.3f}"
    cache = _read_cache()
    if key in cache:
        return cache[key]

    profile = _find_profile(lat, lon)

    cache[key] = profile
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return profile


if __name__ == "__main__":
    place = sys.argv[1] if len(sys.argv) > 1 else "Cluj-Napoca"
    matches = geocode(place)
    if not matches:
        sys.exit(f"No place found for '{place}'")

    top = matches[0]
    print(f"{top['name']}, {top['country']} ({top['lat']:.4f}, {top['lon']:.4f})\n")
    for key, value in get_soil(top["lat"], top["lon"]).items():
        print(f"{key:<22}{value}")