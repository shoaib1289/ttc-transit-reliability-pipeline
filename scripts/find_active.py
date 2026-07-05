import duckdb
c = duckdb.connect("ttc.duckdb")
print(c.sql("""
    SELECT entity.vehicle.trip.routeId AS route, count(*) AS readings
    FROM main.raw_rt_vehicle_positions
    WHERE entity.vehicle.trip.routeId LIKE '3%'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
""").df())
c.close()