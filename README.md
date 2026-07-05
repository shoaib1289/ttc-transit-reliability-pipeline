# TTC Transit Reliability Pipeline

Comparing the TTC's *promised* schedule against *actual* arrivals to measure
how reliable Toronto transit really is, route by route.

Contains information licensed under the Open Government Licence – Toronto.

## Stack
Python (ingestion) → DuckDB (warehouse) → dbt (transform) → dashboard.
Built historical-first for validation, then pointed at the live feed.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2a — load the static schedule (do this first)
1. Download the GTFS zip from https://open.toronto.ca/dataset/ttc-routes-and-schedules/
2. Unzip it into `data/gtfs_static/` (you should see stops.txt, trips.txt, routes.txt, stop_times.txt)
3. Run:
   ```bash
   python scripts/load_static_gtfs.py
   ```
4. The script prints a few routes at the end. **Find the route you ride and note its `route_id`** — you'll scope everything to that one route next.

## What you have after Step 2a
A local `ttc.duckdb` with four raw tables:
`raw_static_routes`, `raw_static_trips`, `raw_static_stops`, `raw_static_stop_times`.

`raw_static_stop_times` is the heart of the "promise": for each trip, the
scheduled arrival time at each stop.

## Next steps
- Step 2b: `pull_historical_rt.py` — pull archived realtime snapshots into `raw/`
- Step 3: explore the data in DuckDB (eyeball one vehicle moving along your route)
- Step 4: `dbt init` and build the staging models
```
