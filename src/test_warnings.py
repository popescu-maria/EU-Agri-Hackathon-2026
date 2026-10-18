from datetime import date, timedelta

from src.engine import analyse_crop
from src.varieties import load_varieties

TODAY = date.today()
NORMALS = {1: -2, 2: 0, 3: 5, 4: 11, 5: 16, 6: 20, 7: 22, 8: 22, 9: 17, 10: 11, 11: 5, 12: 0}
SOIL = {"texture_group": "heavy", "ph": 6.8, "organic_matter": "medium"}


def weather(rain=None, t_min=None, t_max=None, soil_temp=11, et0=1):
    rows = []
    for i in range(-7, 7):
        f = i >= 0
        rows.append({
            "date": (TODAY + timedelta(i)).isoformat(), "is_past": not f,
            "t_min": t_min[i] if f and t_min else 8, "t_max": t_max[i] if f and t_max else 16,
            "rain_mm": rain[i] if f and rain else 0, "et0_mm": et0, "gust_kmh": 20, "soil_temp_c": soil_temp,
        })
    return rows


def show(title, crop, variety, forecast):
    r = analyse_crop(crop, load_varieties()[variety], SOIL, forecast, NORMALS, {}, TODAY)
    print(f"\n== {title}")
    if r.get("sowing"):
        print("  advice:", r["sowing"]["message"])
    for a in r["alerts"]:
        print(f"  {a['level'].upper():8} {a['title']}: {a['message']}")


planned = {"id": "t1", "status": "planned"}
growing = {"id": "t2", "status": "growing", "sowing_date": (TODAY - timedelta(days=160)).isoformat()}

show("Flood in 2 days", planned, "su_karlsson", weather(rain=[0, 0, 35, 4, 0, 0, 0]))
show("Good sowing week", planned, "su_karlsson", weather())
show("Killing frost", growing, "kws_allegro", weather(t_min=[8, 8, -3, 5, 6, 6, 6]))
show("Heat wave", growing, "kws_allegro", weather(t_max=[25, 30, 34, 31, 25, 25, 25]))
show("Dry spell", growing, "kws_allegro", weather(et0=6))
show("Rain at harvest", growing, "kws_donjuan", weather(rain=[0, 0, 12, 0, 0, 0, 0]))