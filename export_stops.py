"""
Export stop coordinates from the GTFS static feed for the dashboard map layer.
Run from project root:  python export_stops.py
"""

import glob
import os

import duckdb

# Find stops.txt inside data/gtfs_static (handles a nested folder)
matches = glob.glob("data/gtfs_static/**/stops.txt", recursive=True)
if not matches:
    raise SystemExit("stops.txt not found under data/gtfs_static — check the path.")

stops_txt = matches[0].replace("\\", "/")
print(f"reading {stops_txt}")

duckdb.sql(
    f"""
    COPY (
        SELECT
            CAST(stop_id AS VARCHAR) AS stop_id,
            CAST(stop_lat AS DOUBLE) AS stop_lat,
            CAST(stop_lon AS DOUBLE) AS stop_lon
        FROM read_csv_auto('{stops_txt}')
        WHERE stop_lat IS NOT NULL AND stop_lon IS NOT NULL
    ) TO 'data/stops.parquet'
    """
)

size_kb = os.path.getsize("data/stops.parquet") / 1024
print(f"wrote data/stops.parquet ({size_kb:.0f} KB)")
