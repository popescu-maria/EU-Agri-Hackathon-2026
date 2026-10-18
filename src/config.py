# Rules behind every warning in the app. Change a number here, restart the server, and the advice changes.

# ---- Frost ----
FROST_LEAD_DAYS = 3          # how many days ahead we look for frost
FROST_WARN_C = 2.0           # night low (°C) that counts as frost for young or flowering plants
FROST_URGENT_C = 0.0         # at or below this, the frost warning becomes urgent
FROST_KILL_MARGIN_C = 1.0    # warn this many °C before the variety's own killing temperature

# ---- Heat ----
HEAT_LEAD_DAYS = 5           # how many days ahead we look for heat
HEAT_WARN_MARGIN_C = 2.0     # warn this many °C below the variety's heat limit

# ---- Dry spell ----
DROUGHT_LOOKBACK_DAYS = 7    # past days used to measure how much water the field lost
DROUGHT_LOOKAHEAD_DAYS = 5   # future days checked for rain that would end the dry spell
DROUGHT_RAIN_RELIEF_MM = 5   # this much rain ahead cancels the warning
DROUGHT_DEFICIT_MM = {"high": (15, 30), "medium": (25, 45), "low": (40, 70)}   # (warning, urgent) water lost, by crop sensitivity
DROUGHT_SOIL_FACTOR = {"light": 0.7, "medium": 1.0, "heavy": 1.2}            # sandy soil dries faster, clay slower

# ---- Heavy rain and flooding ----
HEAVY_RAIN_LEAD_DAYS = 3     # how many days ahead we warn about flooding
HEAVY_RAIN_MM = 20           # rain in one day that can flood a field
FLOOD_2DAY_MM = 30           # rain over two days that can flood a field
FLOOD_URGENT_MM = 40         # at or above this, the flood warning becomes urgent
DRYING_DAYS = {"light": 1, "medium": 2, "heavy": 3}   # days a field needs to dry after heavy rain, by soil type

# ---- Whole-farm warnings (not tied to one crop) ----
STORM_LEAD_DAYS = 3          # how many days ahead we warn about storm winds
STORM_GUST_KMH = 60          # wind gusts at or above this are storm winds
FARM_FROST_C = -2.0          # night frost at or below this: protect pipes, pumps and young plants

# ---- Sowing ----
SOWING_LOOKAHEAD_DAYS = 6    # how many days ahead we look for good sowing days
SOWING_MAX_RAIN_MM = 5       # a day with more rain than this is not a sowing day

# ---- Harvest ----
HARVEST_RAIN_LEAD_DAYS = 3   # how many days ahead we warn about rain during harvest time
HARVEST_RAIN_MM = 5          # rain that makes grain too wet to harvest

# ---- Crop list in the app ----
VARIETIES_PER_CROP = 4       # how many varieties of each crop the app shows
SHOWN_VARIETIES = {          # pick them by id; a crop not listed here shows its first VARIETIES_PER_CROP
    "maize": ["kws_curacao", "kws_allegro", "kws_adonisio", "kws_donjuan"],
    "wheat": ["dropia", "izvor", "mulika", "plasmadur"],
    "rye": ["su_karlsson", "kws_serafino", "kws_valentor", "su_fred"],
}

# ---- Demo mode (for presentations) ----
# Fake weather added on top of the real forecast when "Demo" is switched on in My farm.
# Key = days from today, value = what to change on that day.
DEMO_SCENARIOS = {
    "flood": {
        0: {"rain_mm": 0},
        1: {"rain_mm": 0},
        2: {"rain_mm": 42, "gust_kmh": 75},
        3: {"rain_mm": 12, "t_min": -3},
    },
}