import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.soil import get_soil, organic_matter_level, texture_group, usda_class
from src.weather import geocode

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "processed"
WEATHER_GLOB = "weather_daily_*.csv"
SOIL_FILE = DATA / "soil_soil_topsoil_ready.csv"

WEATHER_COLS = [
    "nuts3_id", "date", "centroid_latitude", "centroid_longitude",
    "temperature_min_c", "temperature_mean_c", "temperature_max_c",
    "precipitation_mm", "reference_evapotranspiration_mm",
    "gdd_base_5_c", "gdd_base_10_c", "frost_day", "heat_day",
]
SOIL_KEYS = [
    "ph", "clay_pct", "sand_pct", "silt_pct", "organic_carbon_g_kg",
    "texture_class", "texture_group", "organic_matter",
]


def _doy_to_mmdd(doy):
    if pd.isna(doy):
        return None
    day = min(int(round(doy)), 365)
    return (datetime(2001, 1, 1) + timedelta(days=day - 1)).strftime("%m-%d")


def _build_soil():
    cols = ["topsoil_clay_g_kg", "topsoil_sand_g_kg", "topsoil_silt_g_kg",
            "topsoil_ph_h2o", "topsoil_organic_carbon_g_kg"]
    soil = pd.read_csv(SOIL_FILE).dropna(subset=cols)

    total = soil["topsoil_clay_g_kg"] + soil["topsoil_sand_g_kg"] + soil["topsoil_silt_g_kg"]
    soil["clay_pct"] = soil["topsoil_clay_g_kg"] / total * 100
    soil["sand_pct"] = soil["topsoil_sand_g_kg"] / total * 100
    soil["silt_pct"] = soil["topsoil_silt_g_kg"] / total * 100
    soil["texture_class"] = [
        usda_class(c, s, z) for c, s, z in zip(soil["clay_pct"], soil["sand_pct"], soil["silt_pct"])
    ]
    soil["texture_group"] = soil["texture_class"].map(texture_group)
    soil["organic_matter"] = soil["topsoil_organic_carbon_g_kg"].map(organic_matter_level)
    soil = soil.rename(columns={
        "topsoil_ph_h2o": "ph",
        "topsoil_organic_carbon_g_kg": "organic_carbon_g_kg",
    })
    soil[["ph", "clay_pct", "sand_pct", "silt_pct", "organic_carbon_g_kg"]] = soil[
        ["ph", "clay_pct", "sand_pct", "silt_pct", "organic_carbon_g_kg"]
    ].round(1)
    return soil[["nuts3_id"] + SOIL_KEYS]


def build():
    files = sorted(DATA.glob(WEATHER_GLOB))
    if not files:
        raise SystemExit(f"No files matching {WEATHER_GLOB} in {DATA}")

    monthly_parts, frost_parts, centroids = [], [], None

    for path in files:
        print(f"Reading {path.name}")
        df = pd.read_csv(path, usecols=WEATHER_COLS, parse_dates=["date"])
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month
        df["doy"] = df["date"].dt.dayofyear

        if centroids is None:
            centroids = df.groupby("nuts3_id")[["centroid_latitude", "centroid_longitude"]].first()

        monthly_parts.append(
            df.groupby(["nuts3_id", "year", "month"]).agg(
                tmin_c=("temperature_min_c", "mean"),
                tmean_c=("temperature_mean_c", "mean"),
                tmax_c=("temperature_max_c", "mean"),
                rain_mm=("precipitation_mm", "sum"),
                et0_mm=("reference_evapotranspiration_mm", "sum"),
                gdd5=("gdd_base_5_c", "sum"),
                gdd10=("gdd_base_10_c", "sum"),
                frost_days=("frost_day", "sum"),
                heat_days=("heat_day", "sum"),
            ).reset_index()
        )

        frost = df[df["frost_day"] == 1]
        spring = frost[frost["month"] <= 6].groupby(["nuts3_id", "year"])["doy"].max().rename("last_spring_frost")
        autumn = frost[frost["month"] >= 7].groupby(["nuts3_id", "year"])["doy"].min().rename("first_autumn_frost")
        frost_parts.append(pd.concat([spring, autumn], axis=1).reset_index())

    OUT.mkdir(parents=True, exist_ok=True)

    climate = (
        pd.concat(monthly_parts)
        .groupby(["nuts3_id", "month"]).mean(numeric_only=True)
        .drop(columns="year").round(1).reset_index()
    )
    climate.to_csv(OUT / "climate_monthly.csv", index=False)

    frost = pd.concat(frost_parts).groupby("nuts3_id").agg(
        last_spring_frost=("last_spring_frost", "median"),
        first_autumn_frost=("first_autumn_frost", "median"),
        years_used=("year", "nunique"),
    ).reset_index()
    frost["last_spring_frost"] = frost["last_spring_frost"].map(_doy_to_mmdd)
    frost["first_autumn_frost"] = frost["first_autumn_frost"].map(_doy_to_mmdd)

    regions = (
        centroids.reset_index()
        .rename(columns={"centroid_latitude": "lat", "centroid_longitude": "lon"})
        .merge(_build_soil(), on="nuts3_id", how="left")
        .merge(frost, on="nuts3_id", how="left")
    )
    regions["country"] = regions["nuts3_id"].str[:2]
    regions.to_csv(OUT / "regions.csv", index=False)

    print(f"Done: {len(regions)} regions, {len(climate)} climate rows, {len(files)} year(s) of weather")


_regions = None
_climate = None


def _load_regions():
    global _regions
    if _regions is None:
        _regions = pd.read_csv(OUT / "regions.csv")
    return _regions


def _load_climate():
    global _climate
    if _climate is None:
        _climate = pd.read_csv(OUT / "climate_monthly.csv")
    return _climate


def _haversine_km(lat, lon, lats, lons):
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lons - lon) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def find_region(lat, lon, max_km=100):
    df = _load_regions()
    dist = _haversine_km(lat, lon, df["lat"].to_numpy(), df["lon"].to_numpy())
    i = int(dist.argmin())
    if dist[i] > max_km:
        return None
    row = {k: (None if pd.isna(v) else v) for k, v in df.iloc[i].to_dict().items()}
    row["distance_km"] = round(float(dist[i]), 1)
    return row


def get_climate(nuts3_id):
    df = _load_climate()
    return df[df["nuts3_id"] == nuts3_id].sort_values("month").reset_index(drop=True)


def soil_with_fallback(lat, lon):
    try:
        return get_soil(lat, lon)
    except Exception:
        region = find_region(lat, lon)
        if region is None or region["ph"] is None:
            raise
        return {**{k: region[k] for k in SOIL_KEYS}, "source": "region_average", "region_id": region["nuts3_id"]}


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "Cluj-Napoca"
    if arg == "build":
        build()
        sys.exit()

    matches = geocode(arg)
    if not matches:
        sys.exit(f"No place found for '{arg}'")
    top = matches[0]
    print(f"{top['name']}, {top['country']} ({top['lat']:.4f}, {top['lon']:.4f})\n")

    region = find_region(top["lat"], top["lon"])
    if region is None:
        sys.exit("No region within 100 km (outside the dataset)")

    print(f"Region {region['nuts3_id']}, centroid {region['distance_km']} km away")
    print(f"Last spring frost  {region['last_spring_frost']}")
    print(f"First autumn frost {region['first_autumn_frost']}  (from {region['years_used']} year(s))\n")
    print("Region soil (hackathon data):")
    for key in SOIL_KEYS:
        print(f"  {key:<22}{region[key]}")
    print("\nClimate by month:")
    print(get_climate(region["nuts3_id"]).drop(columns="nuts3_id").to_string(index=False))