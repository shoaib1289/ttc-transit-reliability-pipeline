import duckdb
c = duckdb.connect("ttc.duckdb")
print("102 positions in staging:")
print(c.sql("SELECT count(*) FROM main.stg_rt__vehicle_positions").df())
print("\n102 arrivals detected:")
print(c.sql("SELECT count(*) FROM main.int_actual_arrivals").df())
print("\n102 stops in schedule:")
print(c.sql("""SELECT count(distinct st.stop_id) FROM main.stg_schedule__stop_times st
    JOIN main.stg_schedule__trips t ON st.trip_id=t.trip_id WHERE t.route_id='102'""").df())
print("\nLatest position time:")
print(c.sql("SELECT max(recorded_at) FROM main.stg_rt__vehicle_positions").df())
import duckdb
c = duckdb.connect("ttc.duckdb")

print("=== 1. RAW: what's actually loaded? ===")
print(c.sql("""
    SELECT count(*) AS total_rows,
           count(distinct filename) AS snapshot_files
    FROM main.raw_rt_vehicle_positions
""").df())

print("\n=== 2. RAW: latest timestamp across ALL vehicles ===")
print(c.sql("""
    SELECT max(to_timestamp(cast(entity.vehicle.timestamp as bigint))) AS latest_any_vehicle
    FROM main.raw_rt_vehicle_positions
""").df())

print("\n=== 3. RAW: how many route-102 readings, and their time range? ===")
print(c.sql("""
    SELECT count(*) AS rows_102,
           min(to_timestamp(cast(entity.vehicle.timestamp as bigint))) AS earliest,
           max(to_timestamp(cast(entity.vehicle.timestamp as bigint))) AS latest
    FROM main.raw_rt_vehicle_positions
    WHERE entity.vehicle.trip.routeId = '102'
""").df())

print("\n=== 4. STAGING: what the staging model outputs ===")
print(c.sql("""
    SELECT count(*) AS rows,
           min(recorded_at) AS earliest,
           max(recorded_at) AS latest
    FROM main.stg_rt__vehicle_positions
""").df())
import duckdb
c = duckdb.connect("ttc.duckdb")

print("Route 102 in raw, extracted the way staging does it:")
print(c.sql("""
    SELECT
        entity.vehicle.trip.routeId AS route_id,
        to_timestamp(cast(entity.vehicle.timestamp as bigint)) AS recorded_at
    FROM main.raw_rt_vehicle_positions
    WHERE entity.vehicle.trip.routeId = '102'
    ORDER BY recorded_at DESC
    LIMIT 5
""").df())

print("\nDoes the staging model still have a route filter? Checking compiled SQL...")
# show the actual route values staging sees
print(c.sql("SELECT DISTINCT route_id FROM main.stg_rt__vehicle_positions").df())

c.close()