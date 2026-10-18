import json
import sys
from datetime import date, timedelta

from src import config as cfg
from src.demo import apply_demo
from src.regions import find_region, get_climate, soil_with_fallback
from src.varieties import load_varieties
from src.weather import get_forecast

LEVEL_RANK = {"urgent": 0, "warning": 1, "info": 2}
PHASES = ["germination", "vegetative", "flowering", "grain_fill"]
MILESTONES = ["emergence", "flowering", "grain_fill", "maturity"]
MAX_HISTORY_DAYS = 92


def _d(text):
    return date.fromisoformat(text)


def _ahead(forecast, today, days):
    end = today + timedelta(days=days)
    return [r for r in forecast if today <= _d(r["date"]) <= end]


def _when(day_text, today):
    delta = (_d(day_text) - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    return _d(day_text).strftime("%A")


def _alert(level, kind, title, message, day):
    return {"level": level, "kind": kind, "title": title, "message": message, "date": day}


def daily_gdd(t_min, t_max, base):
    return max(0.0, (t_min + t_max) / 2 - base)


def gdd_since_sowing(forecast, sowing, today, base, normals):
    rows = {r["date"]: r for r in forecast}
    gdd, day = 0.0, sowing
    while day <= today:
        r = rows.get(day.isoformat())
        if r and r["t_min"] is not None and r["t_max"] is not None:
            gdd += daily_gdd(r["t_min"], r["t_max"], base)
        else:
            gdd += max(0.0, normals[day.month] - base)
        day += timedelta(days=1)
    return gdd


def predict_date(target, gdd_now, forecast, today, normals, base, horizon=400):
    future = {r["date"]: r for r in forecast if _d(r["date"]) > today}
    gdd, day = gdd_now, today
    for _ in range(horizon):
        day += timedelta(days=1)
        row = future.get(day.isoformat())
        if row and row["t_min"] is not None and row["t_max"] is not None:
            gdd += daily_gdd(row["t_min"], row["t_max"], base)
        else:
            gdd += max(0.0, normals[day.month] - base)
        if gdd >= target:
            return day
    return None


def stage_info(gdd, units):
    for phase, milestone in zip(PHASES, MILESTONES):
        if gdd < units[milestone]:
            return phase, milestone
    return "mature", None


def growing_info(v, sowing, forecast, normals, today):
    base = v["growth"]["heat_base_c"]
    units = v["growth"]["heat_units_to_reach"]
    gdd = gdd_since_sowing(forecast, sowing, today, base, normals)
    phase, milestone = stage_info(gdd, units)

    def when_reached(target):
        found = predict_date(target, gdd, forecast, today, normals, base) if milestone else None
        return found.isoformat() if found else None

    return phase, {
        "phase": phase,
        "days_since_sowing": (today - sowing).days,
        "heat_units": round(gdd),
        "progress_pct": min(100, round(gdd / units["maturity"] * 100)),
        "next_milestone": milestone,
        "next_milestone_date": when_reached(units[milestone]) if milestone else None,
        "expected_maturity": when_reached(units["maturity"]),
        "history_truncated": sowing < min(_d(r["date"]) for r in forecast),
    }


CROP_WORD = {"maize": "maize", "wheat": "wheat", "rye": "rye", "barley": "barley"}
PHASE_WORD = {"germination": "sprouting", "vegetative": "leaf growth", "flowering": "flowering", "grain_fill": "grain filling"}


def _crop(v):
    return f"{CROP_WORD.get(v['crop_code'], v['crop_code'])} ({v['variety_name']})"


def _in_days(day_text, today):
    n = (_d(day_text) - today).days
    if n <= 0:
        return "today"
    if n == 1:
        return "tomorrow"
    return f"in {n} days ({_d(day_text).strftime('%A')})"


def _drying_days(soil):
    return cfg.DRYING_DAYS.get(soil.get("texture_group"), 2)


def frost_alert(v, phase, forecast, today):
    ws = v["weather_sensitivity"]
    sensitive = phase in ws["frost_sensitive_phases"]
    kill = ws["frost_kill_temp_c"]
    for r in _ahead(forecast, today, cfg.FROST_LEAD_DAYS):
        t = r["t_min"]
        if t is None:
            continue
        when = _in_days(r["date"], today)
        if kill is not None and t <= kill + cfg.FROST_KILL_MARGIN_C:
            msg = f"Hard frost ({t:.0f} °C) {when} could kill your {_crop(v)}. It survives down to about {kill:.0f} °C."
            return _alert("urgent", "frost", "Killing frost", msg, r["date"])
        if sensitive and t <= cfg.FROST_WARN_C:
            level = "urgent" if t <= cfg.FROST_URGENT_C else "warning"
            msg = f"Frost ({t:.0f} °C) {when}. Your {_crop(v)} is easily damaged by frost during {PHASE_WORD[phase]}."
            return _alert(level, "frost", "Frost risk", msg, r["date"])
    return None


def heat_alert(v, phase, forecast, today):
    ws = v["weather_sensitivity"]
    limit = ws["heat_stress_above_c"]
    if phase not in ws["heat_sensitive_phases"] or limit is None:
        return None
    days = [r for r in _ahead(forecast, today, cfg.HEAT_LEAD_DAYS) if r["t_max"] is not None]
    if not days:
        return None
    r = max(days, key=lambda x: x["t_max"])
    t = r["t_max"]
    if t < limit - cfg.HEAT_WARN_MARGIN_C:
        return None
    level = "urgent" if t >= limit else "warning"
    hint = "" if v["water"]["irrigation"] == "not_needed" else " Water early in the morning if you can."
    msg = f"Very hot ({t:.0f} °C) {_in_days(r['date'], today)}. Heat during {PHASE_WORD[phase]} can lower your {_crop(v)} harvest.{hint}"
    return _alert(level, "heat", "Heat stress", msg, r["date"])


def drought_alert(v, phase, soil, forecast, today):
    ws = v["weather_sensitivity"]
    if phase not in ws["drought_critical_phases"]:
        return None

    start = today - timedelta(days=cfg.DROUGHT_LOOKBACK_DAYS)
    past = [r for r in forecast if start <= _d(r["date"]) < today]
    deficit = sum(r["et0_mm"] or 0 for r in past) - sum(r["rain_mm"] or 0 for r in past)
    rain_ahead = sum(r["rain_mm"] or 0 for r in _ahead(forecast, today, cfg.DROUGHT_LOOKAHEAD_DAYS))
    if rain_ahead >= cfg.DROUGHT_RAIN_RELIEF_MM:
        return None

    warn, urgent = cfg.DROUGHT_DEFICIT_MM[ws["drought_sensitivity"]]
    factor = cfg.DROUGHT_SOIL_FACTOR[soil["texture_group"]]
    if deficit >= urgent * factor:
        level = "urgent"
    elif deficit >= warn * factor:
        level = "warning"
    else:
        return None

    hint = "" if v["water"]["irrigation"] == "not_needed" else " Water now if you can."
    msg = (f"Your field is drying out and little rain is coming. "
           f"Your {_crop(v)} needs water most during {PHASE_WORD[phase]}.{hint}")
    return _alert(level, "drought", "Dry spell", msg, today.isoformat())


def flood_risk(forecast, today, days):
    rows = _ahead(forecast, today, days)
    for i, r in enumerate(rows):
        rain = r["rain_mm"] or 0
        nxt = (rows[i + 1]["rain_mm"] or 0) if i + 1 < len(rows) else 0
        if rain >= cfg.HEAVY_RAIN_MM or (rain >= cfg.SOWING_MAX_RAIN_MM and rain + nxt >= cfg.FLOOD_2DAY_MM):
            return {"date": r["date"], "rain_mm": rain + nxt}
    return None


def rain_alert(v, soil, forecast, today, planned=False):
    sens = v["weather_sensitivity"]["waterlogging_sensitivity"]
    if sens == "low":
        return None
    risk = flood_risk(forecast, today, cfg.HEAVY_RAIN_LEAD_DAYS)
    if risk is None:
        return None
    heavy = soil.get("texture_group") == "heavy"
    level = "urgent" if risk["rain_mm"] >= cfg.FLOOD_URGENT_MM or (heavy and sens == "high") else "warning"
    dry = _drying_days(soil)
    if planned:
        tip = f"Keep machinery off and don't sow your {_crop(v)} until about {dry} days after the rain."
    else:
        tip = f"Clear the ditches so water can drain from your {_crop(v)}, and keep machinery off for about {dry} days."
    msg = f"Wait: heavy rain {_in_days(risk['date'], today)}. The field may flood. {tip}"
    return _alert(level, "flood", "Flood risk", msg, risk["date"])


def _in_harvest(v, day):
    h = v.get("harvest") or {}
    start, end = h.get("window_start"), h.get("window_end")
    return bool(start and end) and start <= day.strftime("%m-%d") <= end


def harvest_alert(v, forecast, today):
    if not _in_harvest(v, today):
        return None
    for r in _ahead(forecast, today, cfg.HARVEST_RAIN_LEAD_DAYS):
        if (r["rain_mm"] or 0) >= cfg.HARVEST_RAIN_MM:
            if _d(r["date"]) == today:
                msg = f"Rain today. Wait until the grain is dry again before you harvest your {_crop(v)}."
            else:
                msg = f"Harvest your {_crop(v)} before {_d(r['date']).strftime('%A')} if you can: rain is coming and wet grain spoils."
            return _alert("warning", "harvest_rain", "Rain at harvest", msg, r["date"])
    return None


def soil_notes(v, soil):
    s, ws = v["soil"], v["weather_sensitivity"]
    notes = []

    ph = soil["ph"]
    best = s.get("ph_best")
    if ph < s["ph_min"] or ph > s["ph_max"]:
        notes.append(("warning", f"Soil pH {ph} is outside the {s['ph_min']}-{s['ph_max']} range this variety tolerates."))
    elif best and not best[0] <= ph <= best[1]:
        notes.append(("info", f"Soil pH {ph} is tolerable but outside the ideal {best[0]}-{best[1]}."))
    else:
        notes.append(("ok", f"Soil pH {ph} suits this variety."))

    group = soil["texture_group"]
    if group in s["texture_best"]:
        notes.append(("ok", f"Your {group} soil is among the best matches for this variety."))
    elif group in s["texture_ok"]:
        notes.append(("info", f"This variety does fine on {group} soil, though it is not its favourite."))
    else:
        notes.append(("warning", f"{group.capitalize()} soil is not among the textures this variety prefers."))

    levels = ["low", "medium", "high"]
    if levels.index(soil["organic_matter"]) < levels.index(s["organic_matter_need"]):
        notes.append(("info", "Organic matter is lower than this variety likes; manure or compost helps."))

    if group == "light" and ws["drought_sensitivity"] == "high":
        notes.append(("info", "Light soil dries out fast, so dry spells will hurt this variety sooner."))
    if group == "heavy" and s["compaction_sensitivity"] == "high":
        notes.append(("info", "Heavy soil compacts when wet; keep machinery off it after rain."))

    return [{"level": level, "text": text} for level, text in notes]


def _in_window(v, day):
    return v["sowing"]["window_start"] <= day.strftime("%m-%d") <= v["sowing"]["window_end"]


def window_state(v, today):
    s = v["sowing"]
    start = date.fromisoformat(f"{today.year}-{s['window_start']}")
    end = date.fromisoformat(f"{today.year}-{s['window_end']}")
    if today < start:
        return {"state": "not_yet", "days": (start - today).days}
    if today <= end:
        return {"state": "open", "days": (end - today).days}
    next_start = date.fromisoformat(f"{today.year + 1}-{s['window_start']}")
    return {"state": "closed", "days": (next_start - today).days}


def _rain_blocked_days(forecast, today, soil):
    dry = _drying_days(soil)
    blocked = set()
    for r in _ahead(forecast, today, cfg.SOWING_LOOKAHEAD_DAYS):
        if (r["rain_mm"] or 0) >= cfg.HEAVY_RAIN_MM:
            day = _d(r["date"])
            for k in range(-1, dry + 1):
                blocked.add((day + timedelta(days=k)).isoformat())
    return blocked


def good_sowing_days(v, forecast, today, soil):
    frost_sensitive = "germination" in v["weather_sensitivity"]["frost_sensitive_phases"]
    blocked = _rain_blocked_days(forecast, today, soil)
    days = []
    for r in _ahead(forecast, today, cfg.SOWING_LOOKAHEAD_DAYS):
        if not _in_window(v, _d(r["date"])) or r["date"] in blocked:
            continue
        if r["soil_temp_c"] is not None and r["soil_temp_c"] < v["sowing"]["min_soil_temp_c"]:
            continue
        if frost_sensitive and r["t_min"] is not None and r["t_min"] <= cfg.FROST_WARN_C:
            continue
        if (r["rain_mm"] or 0) >= cfg.SOWING_MAX_RAIN_MM:
            continue
        days.append(r["date"])
    return days


def _frost_before_sprouting(v, forecast, today):
    if "germination" not in v["weather_sensitivity"]["frost_sensitive_phases"]:
        return None
    for r in _ahead(forecast, today, cfg.SOWING_LOOKAHEAD_DAYS):
        if r["t_min"] is not None and r["t_min"] <= cfg.FROST_WARN_C:
            return r
    return None


def _day_names(days, limit=3):
    return ", ".join(_d(x).strftime("%A") for x in days[:limit])


def _sow_after(best, event_date, gap_days):
    later = [d for d in best if d > event_date]
    return later[0] if later else (_d(event_date) + timedelta(days=gap_days)).isoformat()


def _day_and_date(day_text):
    d = _d(day_text)
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def farm_alerts(forecast, today):
    found = []
    windy = [r for r in _ahead(forecast, today, cfg.STORM_LEAD_DAYS) if (r["gust_kmh"] or 0) >= cfg.STORM_GUST_KMH]
    if windy:
        r = max(windy, key=lambda x: x["gust_kmh"])
        msg = f"Storm winds ({r['gust_kmh']:.0f} km/h) {_in_days(r['date'], today)}. Tie down covers and foil, and keep machinery and animals sheltered."
        found.append(_alert("warning", "wind", "Storm winds", msg, r["date"]))
    cold = [r for r in _ahead(forecast, today, cfg.FROST_LEAD_DAYS) if r["t_min"] is not None and r["t_min"] <= cfg.FARM_FROST_C]
    if cold:
        r = min(cold, key=lambda x: x["t_min"])
        msg = f"Hard frost at night ({r['t_min']:.0f} °C) {_in_days(r['date'], today)}. Protect water pipes and pumps, and cover young plants."
        found.append(_alert("warning", "frost", "Hard frost", msg, r["date"]))
    return found


def sowing_advice(v, forecast, today, region, soil):
    state = window_state(v, today)
    best = good_sowing_days(v, forecast, today, soil)
    crop = _crop(v)
    wait = None

    if state["state"] == "not_yet":
        message = f"Sowing time for your {crop} starts in {state['days']} days."
    elif state["state"] == "closed":
        message = f"Sowing time for your {crop} is over for this year. It starts again in {state['days']} days."
    elif (risk := flood_risk(forecast, today, cfg.SOWING_LOOKAHEAD_DAYS)):
        sow_from = _sow_after(best, risk["date"], _drying_days(soil) + 1)
        wait = {"kind": "flood", "date": risk["date"], "sow_from": sow_from}
        message = (f"Wait: heavy rain {_in_days(risk['date'], today)} may flood the field. "
                   f"Best day to sow your {crop} after the rain: {_day_and_date(sow_from)}, when the field has dried.")
    elif (cold := _frost_before_sprouting(v, forecast, today)):
        sow_from = _sow_after(best, cold["date"], 1)
        wait = {"kind": "frost", "date": cold["date"], "sow_from": sow_from}
        message = (f"Wait: frost ({cold['t_min']:.0f} °C) {_in_days(cold['date'], today)} could kill young plants. "
                   f"Best day to sow your {crop} after the cold: {_day_and_date(sow_from)}.")
    elif best:
        message = f"Good time to sow your {crop}. Best days: {_day_names(best)}."
    else:
        soil_t = [r["soil_temp_c"] for r in _ahead(forecast, today, cfg.SOWING_LOOKAHEAD_DAYS) if r["soil_temp_c"] is not None]
        if soil_t and max(soil_t) < v["sowing"]["min_soil_temp_c"]:
            message = f"The soil is still too cold to sow your {crop}. Wait until it warms up."
        else:
            message = f"This week is not good for sowing your {crop}. Check again in a few days."

    return {
        **state,
        "best_days": best,
        "wait": wait,
        "message": message,
        "typical_last_spring_frost": region.get("last_spring_frost"),
    }


def analyse_crop(crop, v, soil, forecast, normals, region, today):
    result = {
        "crop_id": crop["id"],
        "variety_id": v["id"],
        "variety_name": v["variety_name"],
        "crop_code": v["crop_code"],
        "status": crop["status"],
        "soil_notes": soil_notes(v, soil),
    }

    if crop["status"] == "planned":
        result["sowing"] = sowing_advice(v, forecast, today, region, soil)
        found = []
        if result["sowing"]["state"] == "open":
            found = [frost_alert(v, "germination", forecast, today), rain_alert(v, soil, forecast, today, planned=True)]
    else:
        phase, result["info"] = growing_info(v, _d(crop["sowing_date"]), forecast, normals, today)
        found = []
        if phase != "mature":
            found = [
                frost_alert(v, phase, forecast, today),
                heat_alert(v, phase, forecast, today),
                drought_alert(v, phase, soil, forecast, today),
                rain_alert(v, soil, forecast, today),
            ]
        typical = v["growth"].get("days_to_maturity_typical")
        old_enough = typical is not None and (today - _d(crop["sowing_date"])).days >= typical
        if phase in ("grain_fill", "mature") or old_enough:
            found.append(harvest_alert(v, forecast, today))

    result["alerts"] = sorted(
        (a for a in found if a), key=lambda a: (LEVEL_RANK[a["level"]], a["date"])
    )
    return result


def run(lat, lon, variety_id, sowing_date="planned", today=None):
    today = today or date.today()
    variety = load_varieties()[variety_id]
    soil = soil_with_fallback(lat, lon)
    region = find_region(lat, lon)
    if region is None:
        raise SystemExit("This point is outside the hackathon dataset (no region within 100 km)")

    climate = get_climate(region["nuts3_id"])
    normals = {int(m): float(t) for m, t in zip(climate["month"], climate["tmean_c"])}

    if sowing_date == "planned":
        crop = {"id": "test", "status": "planned"}
        past_days = 7
    else:
        crop = {"id": "test", "status": "growing", "sowing_date": sowing_date}
        age = (today - _d(sowing_date)).days + 1
        past_days = min(max(age, 7), MAX_HISTORY_DAYS)

    forecast = get_forecast(lat, lon, past_days=past_days)
    print(f"Soil: {soil['source']}, {soil.get('distance_km', 'n/a')} km from the point", file=sys.stderr)
    print(f"Region: {region['nuts3_id']} ({region['distance_km']} km to centroid)\n", file=sys.stderr)
    return analyse_crop(crop, variety, soil, forecast, normals, region, today)

def analyse_state(state, today=None):
    today = today or date.today()
    lat, lon = state["location"]["lat"], state["location"]["lon"]
    soil, crops = state["soil"], state["crops"]
    varieties = load_varieties()

    region = find_region(lat, lon)
    if region is None:
        raise ValueError("This point is outside the supported area")

    climate = get_climate(region["nuts3_id"])
    normals = {int(m): float(t) for m, t in zip(climate["month"], climate["tmean_c"])}

    ages = [(today - _d(c["sowing_date"])).days + 1 for c in crops if c["status"] == "growing"]
    forecast = get_forecast(lat, lon, past_days=min(max([7] + ages), MAX_HISTORY_DAYS))
    forecast = apply_demo(forecast, state.get("demo"), today)

    results = [
        analyse_crop(c, varieties[c["variety_id"]], soil, forecast, normals, region, today)
        for c in crops
    ]
    crop_alerts = [{**a, "crop_id": r["crop_id"], "variety_name": r["variety_name"]} for r in results for a in r["alerts"]]
    frost_days = {a["date"] for a in crop_alerts if a["kind"] == "frost"}
    whole_farm = [{**a, "crop_id": None, "variety_name": None} for a in farm_alerts(forecast, today)
                  if not (a["kind"] == "frost" and a["date"] in frost_days)]
    alerts = sorted(
        crop_alerts + whole_farm,
        key=lambda a: (LEVEL_RANK[a["level"]], a["date"]),
    )
    return {
        "today": today.isoformat(),
        "crops": results,
        "alerts": alerts,
        "urgent_count": sum(a["level"] == "urgent" for a in alerts),
    }

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit("Usage: python -m src.engine LAT LON VARIETY_ID [SOWING_DATE|planned]")
    result = run(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3], *sys.argv[4:5])
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))