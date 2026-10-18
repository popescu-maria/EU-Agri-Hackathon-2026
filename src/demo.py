from datetime import date, timedelta

from src import config as cfg


def apply_demo(forecast, scenario, today=None):
    changes = cfg.DEMO_SCENARIOS.get(scenario or "")
    if not changes:
        return forecast
    today = today or date.today()
    by_date = {(today + timedelta(days=k)).isoformat(): v for k, v in changes.items()}
    return [{**r, **by_date.get(r["date"], {})} for r in forecast]