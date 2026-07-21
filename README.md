# TTC Transit Reliability Pipeline

How late are Toronto's buses, really?

The TTC publishes a schedule (when each bus *should* reach each stop) and a live GPS feed (where every bus is right now). But nothing in either feed tells you when a bus *actually arrived* somewhere  that truth has to be reconstructed. This project does that: it accumulates live GPS over time, works out when buses actually reached their stops, compares that against the published schedule, and turns the result into reliability metrics  for the entire TTC surface network.

Built end to end: ingestion, warehouse, transformation, testing, a dashboard, and orchestration.

---

## The headline result

Across **156,215 reconstructed arrivals on 181 routes**, the TTC surface network runs **on-time 74.2%** of the time. The network-wide average delay is essentially **zero minutes**  but that's because early and late arrivals roughly cancel out, not because every bus is punctual. About one arrival in four still falls outside the on-time window (more than a minute early, or more than five minutes late).

The more interesting finding is the *shape* of the misses. Across the least reliable routes, buses tend to run **early** rather than late. Early-running is a genuine reliability failure that on-time-percentage alone can hide: you can't catch a bus that already left.

![Dashboard](docs/dashboard.png)

The project was built and validated on a single route (102, Markham Rd) first, then scaled to all routes  which is where the interesting engineering is.

---

## Why this is harder than it looks

**Arrivals don't exist in the data.** The realtime feed reports vehicle *positions*, not arrivals. So the core of the project is reconstruction: for each GPS ping, measure its distance to the stops on that bus's route, and when a bus comes within ~50 metres of a stop, treat that moment as an arrival. A stream of GPS dots becomes a set of real arrival events.

**The two feeds don't join.** The realtime feed and the schedule use different `trip_id` systems, so they can't be joined directly. Matching each actual arrival to the *nearest scheduled time at the same stop on the same route* solves it  which is also how transit agencies actually measure schedule adherence.

**Scaling breaks the naive approach.** Reconstructing one route is a small cross-join (bus positions × that route's stops). Doing it for all routes naively means every bus position against every stop in the city  roughly 700k × 9,000 = billions of comparisons. Constraining the distance calculation to *same-route* stops brings that back to millions, and the whole network builds in seconds. Similarly, the schedule-matching join initially ran out of memory at city scale; pushing the time-window filter into the join predicate (so each arrival only pairs with nearby scheduled times) brought a 156k-arrival build back into budget.

---

## Architecture

```
  LIVE GPS FEED                         STATIC SCHEDULE (GTFS)
  (TTC, protobuf, ~30s cadence)         (published, ~6-week cadence)
        |                                     |
        v                                     v
  pull_rt.py  -->  raw JSON snapshots    load_static_gtfs.py
        |                                     |
        v                                     v
  raw_rt_vehicle_positions          raw_static_{routes,trips,stops,stop_times}
        |                                     |
        |  (dbt: staging)                     |  (dbt: staging)
        v                                     v
  stg_rt__vehicle_positions          stg_schedule__*
        \                                   /
         \                                 /
          v                               v
              int_actual_arrivals    (reconstruct arrivals; same-route join)
                        |
                        v
              fct_stop_performance   (match to schedule -> compute delay)
                        |
                        v
              fct_route_reliability  (aggregate -> on-time %, avg delay per route/stop/direction)
                        |
                        v
                  dashboard  +  Airflow-orchestrated runs
```

![dbt lineage](docs/lineage.png)

---

## Stack

| Layer | Tool | Why |
|---|---|---|
| Ingestion | Python (requests, gtfs-realtime-bindings) | Polls the live feed; decodes protobuf GPS |
| Warehouse | DuckDB | Free, local, columnar  same paradigm as Snowflake/BigQuery |
| Transformation | dbt | Layered models (staging → intermediate → marts), with tests, docs, snapshots |
| Dashboard | Streamlit | Interactive, pure-Python; network-wide plus per-route drill-down |
| Orchestration | Apache Airflow (Docker) | Scheduled, ordered, monitored pipeline runs |

---

## What it demonstrates

- **Reconstructed data, not a clean dataset.** Actual arrivals are inferred from raw GPS geometry, not read from a feed.
- **Layered dbt modelling**  staging (clean, 1:1), intermediate (the reconstruction logic), marts (delay and aggregation).
- **A parameterized, scalable pipeline**  the route is a dbt variable; the same models run for one route or all 181.
- **Query optimization under real constraints**  same-route joins and a join-predicate time filter keep a city-scale build fast and within memory.
- **Incremental materialization**  the fact table appends only new arrivals as data grows, instead of rebuilding.
- **Automated data-quality tests**  dbt tests (`not_null`, `unique`, `accepted_range`) that still pass at 156k rows across 181 routes.
- **SCD Type 2 snapshot**  captures schedule changes over time (the TTC republishes every ~6 weeks).
- **Direction-aware analysis**  northbound and southbound reliability measured separately.
- **Orchestration**  an Airflow DAG runs load → transform → test in order, on a schedule, with retries.

![Airflow DAG](docs/airflow.png)

---

## Engineering decisions worth noting

- **Arrival detection by proximity.** A bus within ~50 m of a stop counts as arrived. The threshold is documented and validated, because a wrong rule silently corrupts every downstream metric.
- **Schedule/realtime IDs don't reconcile**, so arrivals are matched to the nearest scheduled time at the same stop and route rather than by `trip_id`.
- **Outlier guarding.** Matches more than 30 minutes off are discarded as mismatched trips, which kept impossible values out of the metrics.
- **Out-of-service hours handled correctly.** Buses running outside scheduled service have no schedule to match against and are excluded rather than producing garbage delays.
- **Batch loading.** Loading three hours of data (~722k rows) initially ran out of memory; the loader was refactored to process files in batches.
- **LocalExecutor over CeleryExecutor** for Airflow  a deliberate choice for a single-machine setup on limited RAM.

---

## Running it

```
pip install -r requirements.txt

# 1. Download the TTC GTFS schedule and unzip into data/gtfs_static/
#    https://open.toronto.ca/dataset/ttc-routes-and-schedules/

# 2. Load the schedule
python scripts/load_static_gtfs.py

# 3. Collect live GPS (runs a polling loop)
python scripts/pull_rt.py

# 4. Load the collected snapshots
python scripts/load_rt_snapshots.py

# 5. Build and test the pipeline
cd ttc
dbt run
dbt test

# 6. Launch the dashboard (from the project root)
streamlit run dashboard.py
```

By default the pipeline runs for all routes. To scope to a single route, override the dbt variable: `dbt run --vars '{target_route: "102"}'`. Airflow (optional, for orchestration) lives in `airflow/` and runs via Docker Compose.

---

## Data and licensing

Schedule and realtime data from City of Toronto Open Data / TTC, under the Open Government Licence – Toronto. This project contains information licensed under the Open Government Licence – Toronto.

---

## Roadmap

- Swap DuckDB for a cloud warehouse (Snowflake / BigQuery)  largely a dbt profile change
- Geospatial dashboard: map stops and routes coloured by reliability
- Longer collection windows to surface time-of-day and day-of-week patterns
