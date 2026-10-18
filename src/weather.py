import json
import sys
import time
from pathlib import Path
from statistics import mean

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
TIMEOUT = 10

DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "et0_fao_evapotranspiration",
    "wind_gusts_10m_max",
]


def _get_with_retry(url, params, attempts=3):
    for i in range(attempts):
        r = requests.get(url, params=params, timeout=TIMEOUT)
        if r.status_code not in (429, 500, 502, 503, 504):
            break
        time.sleep(2 ** i)
    if not r.ok:
        raise RuntimeError(f"Weather API error {r.status_code}: {r.text[:200]}")
    return r


def geocode(name, count=5):
    r = _get_with_retry(
        GEOCODE_URL,
        {"name": name, "count": count, "language": "en", "format": "json"},
    )
    return [
        {
            "name": p["name"],
            "region": p.get("admin1"),
            "country": p.get("country"),
            "lat": p["latitude"],
            "lon": p["longitude"],
        }
        for p in r.json().get("results", [])
    ]


def _daily_mean(times, values):
    by_day = {}
    for t, v in zip(times, values):
        if v is not None:
            by_day.setdefault(t[:10], []).append(v)
    return {day: round(mean(vals), 1) for day, vals in by_day.items()}


def _fetch_forecast(params):
    cache_file = CACHE_DIR / f"forecast_{params['latitude']:.2f}_{params['longitude']:.2f}_{params['past_days']}.json"
    try:
        data = _get_with_retry(FORECAST_URL, params).json()
    except (RuntimeError, requests.RequestException):
        if cache_file.exists():
            print("Weather API unavailable, using the saved forecast", file=sys.stderr)
            return json.loads(cache_file.read_text(encoding="utf-8"))
        raise
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    return data


def get_forecast(lat, lon, past_days=7, forecast_days=7):
    data = _fetch_forecast({
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(DAILY_VARS),
        "hourly": "soil_temperature_6cm",
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": "auto",
    })

    daily, hourly = data["daily"], data["hourly"]
    soil = _daily_mean(hourly["time"], hourly["soil_temperature_6cm"])

    return [
        {
            "date": date,
            "is_past": i < past_days,
            "t_min": daily["temperature_2m_min"][i],
            "t_max": daily["temperature_2m_max"][i],
            "rain_mm": daily["precipitation_sum"][i],
            "et0_mm": daily["et0_fao_evapotranspiration"][i],
            "gust_kmh": daily["wind_gusts_10m_max"][i],
            "soil_temp_c": soil.get(date),
        }
        for i, date in enumerate(daily["time"])
    ]


if __name__ == "__main__":
    place = sys.argv[1] if len(sys.argv) > 1 else "Vienna"
    matches = geocode(place)
    if not matches:
        sys.exit(f"No place found for '{place}'")

    top = matches[0]
    print(f"{top['name']}, {top['region']}, {top['country']} ({top['lat']:.4f}, {top['lon']:.4f})\n")
    print(f"{'date':<11}{'':<5}{'tmin':>6}{'tmax':>6}{'rain':>7}{'et0':>6}{'gust':>6}{'soil':>6}")
    for d in get_forecast(top["lat"], top["lon"]):
        tag = "past" if d["is_past"] else "fcst"
        print(
            f"{d['date']:<11}{tag:<5}{d['t_min']:>6}{d['t_max']:>6}"
            f"{d['rain_mm']:>7}{d['et0_mm']:>6}{d['gust_kmh']:>6}{str(d['soil_temp_c']):>6}"
        )