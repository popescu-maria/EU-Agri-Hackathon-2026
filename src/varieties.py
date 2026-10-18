import json
from datetime import datetime
from pathlib import Path

VARIETIES_DIR = Path(__file__).resolve().parent.parent / "data"

LEVELS = {"low", "medium", "high"}
SEASONS = {"autumn", "spring"}
LEGACY_SEASONS = {"winter": "autumn", "summer": "spring"}
CATEGORIES = {"cultivated", "cut", "perennial"}
MATURITY = {"very_early", "early", "medium", "late"}
PHASES = {"germination", "vegetative", "flowering", "grain_fill"}
PHASE_ORDER = ["germination", "vegetative", "flowering", "grain_fill"]
TEXTURES = {"light", "medium", "heavy"}
IRRIGATION = {"not_needed", "helpful", "essential"}
MILESTONES = ["emergence", "flowering", "grain_fill", "maturity"]
REQUIRED = [
    "id", "crop_code", "variety_name", "season_type", "category", "sowing",
    "growth", "weather_sensitivity", "water", "soil", "rotation", "harvest", "meta",
]


DEFAULT_SENSITIVE = {
    "wheat": {"frost": ["flowering"], "heat": ["flowering", "grain_fill"], "drought": ["flowering", "grain_fill"]},
    "maize": {"frost": ["germination", "vegetative"], "heat": ["flowering"], "drought": ["flowering", "grain_fill"]},
    "rye": {"frost": ["flowering"], "heat": ["flowering", "grain_fill"], "drought": ["flowering", "grain_fill"]},
    "barley": {"frost": ["flowering"], "heat": ["flowering", "grain_fill"], "drought": ["flowering", "grain_fill"]},
}


def _valid_date(text):
    try:
        datetime.strptime(f"2000-{text}", "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _convert(v):
    vid = v["variety_id"]
    phases = v["phases"]
    bounds = [phases[p]["gdd_from_sowing"] for p in PHASE_ORDER]

    for (_, end), (start, _) in zip(bounds, bounds[1:]):
        if end != start:
            raise ValueError(f"{vid}: phases must follow each other without gaps ({bounds})")

    units = v["growth"]["heat_units_to_reach"]
    if units["emergence"] != bounds[0][1] or units["maturity"] != bounds[3][1]:
        raise ValueError(f"{vid}: heat_units_to_reach emergence/maturity do not match the phase boundaries")
    if not bounds[2][0] <= units["flowering"] <= bounds[2][1]:
        raise ValueError(f"{vid}: heat_units_to_reach.flowering is outside the flowering phase")

    sens = v.get("sensitive_phases") or DEFAULT_SENSITIVE.get(v["crop_code"])
    if sens is None:
        raise ValueError(f"{vid}: add a 'sensitive_phases' block (frost, heat, drought) for crop '{v['crop_code']}'")

    window = v["harvest"]["window"]
    verification = v.get("verification", {})
    return {
        "id": vid,
        "crop_code": v["crop_code"],
        "subtype": v.get("subtype"),
        "variety_name": v["variety_name"],
        "season_type": v["season_type"],
        "category": v["category"],
        "maturity_group": v.get("maturity_group"),
        "fao_number": v.get("fao_number"),
        "sowing": dict(v["sowing"]),
        "growth": {
            "heat_base_c": v["growth"]["heat_base_c"],
            "heat_units_to_reach": {
                "emergence": bounds[0][1],
                "flowering": bounds[2][0],
                "grain_fill": bounds[3][0],
                "maturity": bounds[3][1],
            },
            "days_to_maturity_typical": v.get("days_to_maturity_typical"),
        },
        "weather_sensitivity": {
            "frost_tolerance": v["frost_tolerance"],
            "frost_kill_temp_c": v.get("frost_kill_temp_c"),
            "frost_sensitive_phases": sens["frost"],
            "heat_stress_above_c": v.get("heat_stress_above_c"),
            "heat_sensitive_phases": sens["heat"],
            "drought_sensitivity": v["drought_sensitivity"],
            "drought_critical_phases": sens["drought"],
            "waterlogging_sensitivity": v["waterlogging_sensitivity"],
        },
        "water": v["water"],
        "soil": {
            **v["soil"],
            "organic_matter_need": v["organic_matter_need"],
            "compaction_sensitivity": v["compaction_sensitivity"],
        },
        "rotation": v["rotation"],
        "harvest": {"window_start": window[0], "window_end": window[1]},
        "buying": {"order_months": v.get("order_months")},
        "main_regions": v.get("main_regions", []),
        "meta": {
            "source": ", ".join(verification.get("source_ids", [])) or None,
            "verification": verification.get("status", "unverified"),
            "confidence": v.get("confidence"),
            "notes": v.get("notes", ""),
        },
    }


def _legacy(v):
    season = LEGACY_SEASONS.get(v["season_type"], v["season_type"])
    return {
        **v,
        "season_type": season,
        "subtype": None,
        "main_regions": [],
        "meta": {**v["meta"], "verification": "unverified"},
    }


def validate(v):
    missing = [k for k in REQUIRED if k not in v]
    if missing:
        return [f"{v.get('id', '?')}: missing {missing}"]

    errors = []

    def check(value, allowed, name):
        values = value if isinstance(value, list) else [value]
        bad = [x for x in values if x is not None and x not in allowed]
        if bad:
            errors.append(f"{v['id']}: {name} has {bad}, allowed {sorted(allowed)}")

    ws, soil = v["weather_sensitivity"], v["soil"]
    check(v["season_type"], SEASONS, "season_type")
    check(v["category"], CATEGORIES, "category")
    check(v.get("maturity_group"), MATURITY, "maturity_group")
    check(ws["frost_tolerance"], LEVELS, "frost_tolerance")
    check(ws["drought_sensitivity"], LEVELS, "drought_sensitivity")
    check(ws["waterlogging_sensitivity"], LEVELS, "waterlogging_sensitivity")
    check(ws["frost_sensitive_phases"], PHASES, "frost_sensitive_phases")
    check(ws["heat_sensitive_phases"], PHASES, "heat_sensitive_phases")
    check(ws["drought_critical_phases"], PHASES, "drought_critical_phases")
    check(v["water"]["irrigation"], IRRIGATION, "irrigation")
    check(soil["texture_best"], TEXTURES, "texture_best")
    check(soil["texture_ok"], TEXTURES, "texture_ok")
    check(soil["organic_matter_need"], LEVELS, "organic_matter_need")
    check(soil["compaction_sensitivity"], LEVELS, "compaction_sensitivity")

    for section in ("sowing", "harvest"):
        for key in ("window_start", "window_end"):
            if not _valid_date(v[section].get(key)):
                errors.append(f"{v['id']}: {section}.{key} must be MM-DD")

    numbers = {
        "sowing.min_soil_temp_c": v["sowing"].get("min_soil_temp_c"),
        "growth.heat_base_c": v["growth"].get("heat_base_c"),
        "soil.ph_min": soil.get("ph_min"),
        "soil.ph_max": soil.get("ph_max"),
    }
    for m in MILESTONES:
        numbers[f"heat_units_to_reach.{m}"] = v["growth"]["heat_units_to_reach"].get(m)
    for name, value in numbers.items():
        if not _is_number(value):
            errors.append(f"{v['id']}: {name} is required and must be a number")

    units = [v["growth"]["heat_units_to_reach"].get(m) for m in MILESTONES]
    if all(_is_number(u) for u in units) and units != sorted(units):
        errors.append(f"{v['id']}: heat_units_to_reach must increase {MILESTONES}")

    if _is_number(soil.get("ph_min")) and _is_number(soil.get("ph_max")) and soil["ph_min"] >= soil["ph_max"]:
        errors.append(f"{v['id']}: ph_min must be below ph_max")

    return errors


def load_varieties(directory=VARIETIES_DIR):
    files = sorted(Path(directory).glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No variety files in {directory}")

    varieties, errors = {}, []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data["varieties"] if isinstance(data, dict) else data
        for raw in items:
            try:
                v = _convert(raw) if "variety_id" in raw else _legacy(raw)
            except (KeyError, ValueError, TypeError) as e:
                errors.append(f"{path.name}: {raw.get('variety_id') or raw.get('id', '?')}: {type(e).__name__} {e}")
                continue
            errors += [f"{path.name}: {e}" for e in validate(v)]
            if v["id"] in varieties:
                errors.append(f"{path.name}: duplicate id {v['id']}")
            varieties[v["id"]] = v

    if errors:
        raise ValueError("Invalid variety data:\n" + "\n".join(errors))
    return varieties


def list_varieties(crop_code=None, season_type=None):
    return [
        v for v in load_varieties().values()
        if (crop_code is None or v["crop_code"] == crop_code)
        and (season_type is None or v["season_type"] == season_type)
    ]


if __name__ == "__main__":
    for v in list_varieties():
        print(f"{v['id']:<20} {v['crop_code']:<7} {str(v['subtype']):<7} {v['season_type']:<7} "
              f"{str(v['maturity_group']):<7} {v['meta']['verification']}")