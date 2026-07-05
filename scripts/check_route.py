"""Quick check: show the schedule for one route. Usage: python scripts/check_route.py 102"""
import duckdb, sys
from pathlib import Path

ROUTE = sys.argv[1] if len(sys.argv) > 1 else "102"
DB = Path(__file__).resolve().parents[1] / "ttc.duckdb"
con = duckdb.connect(str(DB))

print(f"\n=== Route {ROUTE} ===")
print(con.execute("""
    SELECT route_id, route_short_name, route_long_name
    FROM raw_static_routes WHERE route_id = ?
""", [ROUTE]).fetchall())

n_trips = con.execute("""
    SELECT count(*) FROM raw_static_trips WHERE route_id = ?
""", [ROUTE]).fetchone()[0]
print(f"\nScheduled trips on route {ROUTE}: {n_trips:,}")

print(f"\nSample scheduled stop times (the 'promise'):")
rows = con.execute("""
    SELECT st.trip_id, st.stop_sequence, st.arrival_time, s.stop_name
    FROM raw_static_stop_times st
    JOIN raw_static_trips t ON st.trip_id = t.trip_id
    JOIN raw_static_stops s ON st.stop_id = s.stop_id
    WHERE t.route_id = ?
    ORDER BY st.trip_id, st.stop_sequence
    LIMIT 8
""", [ROUTE]).fetchall()
for r in rows:
    print("  ", r)
con.close()
