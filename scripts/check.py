import duckdb
c = duckdb.connect("ttc.duckdb", read_only=True)

print("=== fct_stop_performance (the delay table) ===")
print(c.sql("SELECT count(*) AS arrivals, min(actual_arrival) AS earliest, max(actual_arrival) AS latest FROM main.fct_stop_performance").df())

print("\n=== Route 102 overall reliability ===")
print(c.sql("""
    SELECT count(*) AS stop_dir_combos,
           round(avg(avg_delay_min),2) AS route_avg_delay,
           round(100.0*sum(on_time_count)/sum(total_arrivals),1) AS on_time_pct
    FROM main.fct_route_reliability
""").df())

print("\n=== Now the worst stops actually populate (>=3 arrivals) ===")
print(c.sql("""
    SELECT stop_name, direction_id, total_arrivals, avg_delay_min, on_time_pct
    FROM main.fct_route_reliability
    WHERE total_arrivals >= 3
    ORDER BY on_time_pct ASC
    LIMIT 10
""").df().to_string())
c.close()