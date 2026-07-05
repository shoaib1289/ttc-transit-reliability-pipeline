import duckdb
c = duckdb.connect("ttc.duckdb")

# how many route-102 readings in ALL data, and their time range?
print("Route 102 positions (all data):")
print(c.sql("""
    SELECT count(*) AS rows,
           min(recorded_at) AS earliest,
           max(recorded_at) AS latest
    FROM main.stg_rt__vehicle_positions
""").df())

# how many distinct buses tonight vs total
print("\nRoute 102 readings by hour:")
print(c.sql("""
    SELECT extract(hour from recorded_at) AS hour,
           count(*) AS readings,
           count(distinct vehicle_id) AS buses
    FROM main.stg_rt__vehicle_positions
    GROUP BY 1 ORDER BY 1
""").df())
c.close()

import duckdb
c = duckdb.connect("ttc.duckdb")

# How many arrivals does int_actual_arrivals detect, by hour?
print("Detected arrivals (int_actual_arrivals) by hour:")
print(c.sql("""
    SELECT extract(hour from actual_arrival) AS hour, count(*) AS arrivals
    FROM main.int_actual_arrivals
    GROUP BY 1 ORDER BY 1
""").df())

# What's the max in the final table vs the intermediate?
print("\nMax arrival — intermediate vs final mart:")
print(c.sql("SELECT max(actual_arrival) AS int_max FROM main.int_actual_arrivals").df())
print(c.sql("SELECT max(actual_arrival) AS fct_max FROM main.fct_stop_performance").df())
c.close()

import duckdb
c = duckdb.connect("ttc.duckdb")

# For tonight's arrivals, what's the nearest scheduled gap?
print("Tonight's arrivals and their nearest scheduled gap (minutes):")
print(c.sql("""
    with actual as (
        select stop_id, actual_arrival,
            extract(hour from actual_arrival)*3600 + extract(minute from actual_arrival)*60 as actual_secs
        from main.int_actual_arrivals
        where extract(hour from actual_arrival) in (0,1)
    ),
    scheduled as (
        select st.stop_id,
            cast(split_part(st.scheduled_arrival_str,':',1) as int)*3600
            + cast(split_part(st.scheduled_arrival_str,':',2) as int)*60 as sched_secs
        from main.stg_schedule__stop_times st
        join main.stg_schedule__trips t on st.trip_id=t.trip_id
        where t.route_id='102'
    )
    select round(min(abs(a.actual_secs - s.sched_secs))/60.0,1) as nearest_gap_min
    from actual a join scheduled s on a.stop_id=s.stop_id
""").df())
c.close()