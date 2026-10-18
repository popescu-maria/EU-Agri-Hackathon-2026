from datetime import date, timedelta

from src.engine import drought_alert, frost_alert, heat_alert, rain_alert
from src.varieties import load_varieties

TODAY = date(2027, 7, 1)
SOIL = {"texture_group": "medium"}
MAIZE = load_varieties()["MAIZ_FAO300_TEST"]


def make_forecast(changes=None):
    changes = changes or {}
    rows = []
    for i in range(-7, 8):
        row = {
            "date": (TODAY + timedelta(days=i)).isoformat(),
            "is_past": i < 0,
            "t_min": 12.0, "t_max": 24.0, "rain_mm": 0.0,
            "et0_mm": 5.0, "gust_kmh": 20.0, "soil_temp_c": 18.0,
        }
        row.update(changes.get(i, {}))
        rows.append(row)
    return rows


def show(name, alert):
    text = "no alert" if alert is None else f"{alert['level']:<8} {alert['message']}"
    print(f"{name:<26}{text}")


show("frost (germination)", frost_alert(MAIZE, "germination", make_forecast({1: {"t_min": -1.0}}), TODAY))
show("frost (flowering, mild)", frost_alert(MAIZE, "flowering", make_forecast({1: {"t_min": 1.0}}), TODAY))
show("heat (flowering)", heat_alert(MAIZE, "flowering", make_forecast({2: {"t_max": 34.0}}), TODAY))
show("heat (vegetative)", heat_alert(MAIZE, "vegetative", make_forecast({2: {"t_max": 34.0}}), TODAY))
show("drought (flowering, dry)", drought_alert(MAIZE, "flowering", SOIL, make_forecast(), TODAY))
show("drought (rain coming)", drought_alert(MAIZE, "flowering", SOIL, make_forecast({1: {"rain_mm": 10.0}}), TODAY))
show("drought (vegetative)", drought_alert(MAIZE, "vegetative", SOIL, make_forecast(), TODAY))
show("heavy rain", rain_alert(MAIZE, SOIL, make_forecast({1: {"rain_mm": 25.0}}), TODAY))
show("frost (near kill temp)", frost_alert(MAIZE, "flowering", make_forecast({1: {"t_min": -1.5}}), TODAY))