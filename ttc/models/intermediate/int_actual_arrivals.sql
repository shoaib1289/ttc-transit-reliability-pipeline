-- Reconstructs actual arrivals for ALL routes.
-- Key optimization: buses are matched only to stops ON THEIR OWN ROUTE,
-- so the distance calc stays tractable at city scale.

with bus_positions as (
    select vehicle_id, route_id, trip_id, latitude, longitude, recorded_at
    from {{ ref('stg_rt__vehicle_positions') }}
),

-- every route's stops, WITH the route_id so we can join on it
route_stops as (
    select distinct
        t.route_id,
        s.stop_id,
        s.stop_name,
        s.stop_latitude,
        s.stop_longitude
    from {{ ref('stg_schedule__stops') }} s
    join {{ ref('stg_schedule__stop_times') }} st on s.stop_id = st.stop_id
    join {{ ref('stg_schedule__trips') }} t        on st.trip_id = t.trip_id
),

-- distance from each bus to stops ON ITS OWN ROUTE only (join on route_id!)
distances as (
    select
        b.vehicle_id,
        b.route_id,
        b.trip_id,
        b.recorded_at,
        s.stop_id,
        s.stop_name,
        sqrt(
            power((b.latitude  - s.stop_latitude)  * 111000, 2) +
            power((b.longitude - s.stop_longitude) * 81000, 2)
        ) as distance_m
    from bus_positions b
    join route_stops s on b.route_id = s.route_id      -- <<< the optimization
),

arrivals_raw as (
    select * from distances where distance_m <= 50
),

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

actual_arrivals as (
    select
        vehicle_id,
        route_id,
        trip_id,
        stop_id,
        stop_name,
        min(recorded_at) as actual_arrival,
        min(distance_m)  as closest_distance_m
    from nearest_only
    group by vehicle_id, route_id, trip_id, stop_id, stop_name
)

select * from actual_arrivals