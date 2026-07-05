-- Reconstructs ACTUAL arrivals from raw GPS:
-- a bus within ~50m of a route-102 stop = "arrived" at that stop.

with bus_positions as (
    select vehicle_id, trip_id, latitude, longitude, recorded_at
    from {{ ref('stg_rt__vehicle_positions') }}
),

-- the stops that belong to route 102 (with their coordinates)
route_102_stops as (
    select distinct
        s.stop_id,
        s.stop_name,
        s.stop_latitude,
        s.stop_longitude
    from {{ ref('stg_schedule__stops') }} s
    join {{ ref('stg_schedule__stop_times') }} st on s.stop_id = st.stop_id
    join {{ ref('stg_schedule__trips') }} t        on st.trip_id = t.trip_id
    where t.route_id = '102'
),

-- distance from every bus reading to every 102 stop (flat-earth approx, metres)
distances as (
    select
        b.vehicle_id,
        b.trip_id,
        b.recorded_at,
        s.stop_id,
        s.stop_name,
        sqrt(
            power((b.latitude  - s.stop_latitude)  * 111000, 2) +
            power((b.longitude - s.stop_longitude) * 81000, 2)
        ) as distance_m
    from bus_positions b
    cross join route_102_stops s
),

-- keep only "close enough" hits
arrivals_raw as (
    select *
    from distances
    where distance_m <= 50
),

-- DEDUP: for each bus at each moment, keep only the SINGLE closest stop.
-- (TTC lists multi-sided stops as separate stop_ids a few metres apart,
--  so one bus position can match several — we take the nearest.)
ranked as (
    select *,
        row_number() over (
            partition by vehicle_id, trip_id, recorded_at
            order by distance_m
        ) as rn
    from arrivals_raw
),

nearest_only as (
    select * from ranked where rn = 1
),

-- earliest qualifying moment per bus-trip-stop = the actual arrival
actual_arrivals as (
    select
        vehicle_id,
        trip_id,
        stop_id,
        stop_name,
        min(recorded_at) as actual_arrival,
        min(distance_m)  as closest_distance_m
    from nearest_only
    group by vehicle_id, trip_id, stop_id, stop_name
)

select * from actual_arrivals