# Stream – Farm Planner

A user-friendly farming app that helps you:
Plan your farming activities
Prepare for adverse weather in advance (droughts, frosts, floods, etc.)
Protect your crops based on tailored recommendations

## Requirements

- Python 3.11+
- Internet connection (live weather and soil data)

## Run the app

```bash
git clone https://github.com/popescu-maria/EU-Agri-Hackathon-2026.git
cd EU-Agri-Hackathon-2026

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
python -m uvicorn src.api:app --reload
```

Open **http://127.0.0.1:8000** in your browser.

## Rebuild the regional data (optional)

`data/processed/` is already included. To rebuild it from the hackathon weather and soil files in `data/`:

```bash
python -m src.regions build
```

## Demo mode

In the app, go to **My farm → For presentations → Flood demo**. This adds a fake storm to the real forecast (heavy rain, strong wind and a night frost), so all warnings can be shown live.

## Change the rules

All warning thresholds (frost, heat, rain, sowing, demo storm) are in **`src/config.py`**.

## Test the warnings

```bash
python -m src.test_warnings
```

## Where we take it next
 
- **User accounts and a database:** remember everything about each farmer (fields, crops, sowing dates, past seasons, warnings received), not just what one browser stores.
- **Smarter advice:** use each farmer's history to learn from real results, not only from forecasts.
- **Farmer network:** connect neighbours with the same crops or the same flood risk, so they can share tips and warn each other about local problems.
- **Push notifications:** send flood and frost warnings to the farmer's phone even when the app is closed.

## Data sources

- **Hackathon dataset:** 5 years of daily weather and topsoil data per NUTS3 region (climate, frost dates, supported area)
- **Open-Meteo:** live 7-day forecast and recent weather
- **SoilGrids (ISRIC):** soil at the exact field location
- **Crop variety files:** `data/*_varieties_europe.json`, curated by our team
