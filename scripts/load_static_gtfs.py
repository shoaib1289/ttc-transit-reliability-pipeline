"""
load_static_gtfs.py
-------------------
Loads the TTC static GTFS schedule (the "promise") into a local DuckDB
warehouse as raw tables.

Usage:
    1. Download the GTFS zip from open.toronto.ca (you've done this).
    2. Unzip it into:  data/gtfs_static/
       You should see files like stops.txt, trips.txt, routes.txt, stop_times.txt
    3. Run:  python scripts/load_static_gtfs.py

This is idempotent: re-running drops and reloads the raw_static tables,
so it's safe to run every time the TTC publishes a new schedule (~every 6 weeks).
"""

import duckdb
from pathlib import Path

# ---- config -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GTFS_DIR = PROJECT_ROOT / "data" / "gtfs_static"
DB_PATH = PROJECT_ROOT / "ttc.duckdb"

# The GTFS files we care about for this project. GTFS has more, but these
# are the ones the reliability analysis needs. Each becomes a raw_static_* table.
GTFS_FILES = {
    "routes":     "routes.txt",      # route definitions (route_id, route_short_name, ...)
    "trips":      "trips.txt",       # one row per scheduled vehicle run (trip_id -> route_id)
    "stops":      "stops.txt",       # stop locations (stop_id, stop_lat, stop_lon, stop_name)
    "stop_times": "stop_times.txt",  # THE schedule: trip_id x stop_id x arrival_time  <-- the "promise"
}
# -------------------------------------------------------------------------


def load():
    if not GTFS_DIR.exists():
        raise SystemExit(
            f"GTFS folder not found: {GTFS_DIR}\n"
            f"Unzip your downloaded GTFS file into that folder first."
        )

    con = duckdb.connect(str(DB_PATH))
    print(f"Connected to warehouse: {DB_PATH}")

    for table_suffix, filename in GTFS_FILES.items():
        path = GTFS_DIR / filename
        if not path.exists():
            print(f"  ! skipping {filename} (not found in {GTFS_DIR})")
            continue

        table = f"raw_static_{table_suffix}"
        # read_csv_auto handles GTFS quoting/types; all_varchar keeps things
        # lossless at the raw layer — we cast properly later in dbt staging.
        con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute(f"""
            CREATE TABLE {table} AS
            SELECT * FROM read_csv_auto('{path.as_posix()}', all_varchar=true)
        """)
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  loaded {table:<28} {n:>9,} rows")

    con.close()
    print("Done. Raw static schedule is in DuckDB.")


def peek():
    """Quick sanity check — list routes so you can find YOUR route_id."""
    con = duckdb.connect(str(DB_PATH))
    print("\nA few routes (find the one you ride):")
    rows = con.execute("""
        SELECT route_id, route_short_name, route_long_name
        FROM raw_static_routes
        ORDER BY route_short_name
        LIMIT 20
    """).fetchall()
    for r in rows:
        print("  ", r)
    con.close()


if __name__ == "__main__":
    load()
    peek()
