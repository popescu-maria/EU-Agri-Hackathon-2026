from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import config as cfg
from src.demo import apply_demo
from src.engine import analyse_state
from src.regions import find_region, soil_with_fallback
from src.varieties import load_varieties
from src.weather import get_forecast

app = FastAPI(title="Farm advisor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Location(BaseModel):
    lat: float
    lon: float


class Crop(BaseModel):
    id: str
    variety_id: str
    status: Literal["growing", "planned"]
    sowing_date: Optional[date] = None


class AnalyseRequest(BaseModel):
    location: Location
    soil: dict
    crops: list[Crop]
    today: Optional[date] = None
    demo: Optional[str] = None


def _shown(varieties):
    picked, count = [], {}
    for v in varieties:
        wanted = cfg.SHOWN_VARIETIES.get(v["crop_code"])
        if wanted is not None:
            if v["id"] in wanted:
                picked.append(v)
        elif count.get(v["crop_code"], 0) < cfg.VARIETIES_PER_CROP:
            count[v["crop_code"]] = count.get(v["crop_code"], 0) + 1
            picked.append(v)
    return picked


@app.get("/api/varieties")
def varieties():
    return [
        {
            "id": v["id"],
            "crop_code": v["crop_code"],
            "name": v["variety_name"],
            "season_type": v["season_type"],
            "maturity_group": v.get("maturity_group"),
            "fao_number": v.get("fao_number"),
            "subtype": v.get("subtype"),
            "confidence": v["meta"].get("confidence"),
            "sowing_window": [v["sowing"]["window_start"], v["sowing"]["window_end"]],
            "days_to_maturity": v["growth"].get("days_to_maturity_typical"),
        }
        for v in _shown(load_varieties().values())
    ]


@app.post("/api/setup")
def setup(loc: Location):
    region = find_region(loc.lat, loc.lon)
    if region is None:
        raise HTTPException(422, "This location is outside the supported area")
    try:
        soil = soil_with_fallback(loc.lat, loc.lon)
    except Exception as e:
        raise HTTPException(502, f"Soil lookup failed: {e}")
    return {
        "soil": soil,
        "region": {
            "id": str(region["nuts3_id"]),
            "distance_km": float(region["distance_km"]),
            "last_spring_frost": region["last_spring_frost"],
            "first_autumn_frost": region["first_autumn_frost"],
            "years_used": int(region["years_used"]) if region.get("years_used") else None,
        },
    }


@app.post("/api/analyse")
def analyse(req: AnalyseRequest):
    known = load_varieties()
    for c in req.crops:
        if c.variety_id not in known:
            raise HTTPException(400, f"Unknown variety: {c.variety_id}")
        if c.status == "growing" and c.sowing_date is None:
            raise HTTPException(400, f"Crop {c.id} is growing but has no sowing_date")
    try:
        return analyse_state(req.model_dump(mode="json"), req.today)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"Analysis failed: {e}")


@app.get("/api/weather")
def weather(lat: float, lon: float, demo: Optional[str] = None):
    try:
        days = apply_demo(get_forecast(lat, lon, past_days=1, forecast_days=7), demo)
    except Exception as e:
        raise HTTPException(502, f"Weather lookup failed: {e}")
    return {"days": [d for d in days if not d["is_past"]]}


UI_DIR = Path(__file__).resolve().parent.parent / "ui"
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")