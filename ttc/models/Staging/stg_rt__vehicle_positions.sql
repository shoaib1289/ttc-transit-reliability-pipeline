-- Flattens raw RT snapshots into one clean row per route-102 vehicle per snapshot.
-- This is the "reality" half: where each bus actually was, minute by minute.

with source as (
    select entity from {{ source('ttc_raw', 'raw_rt_vehicle_positions') }}
),

extracted as (
    select
        entity.vehicle.trip.routeId          as route_id,
        entity.vehicle.trip.tripId           as trip_id,
        entity.vehicle.vehicle.id            as vehicle_id,
        cast(entity.vehicle.position.latitude  as double) as latitude,
        cast(entity.vehicle.position.longitude as double) as longitude,
        to_timestamp(cast(entity.vehicle.timestamp as bigint)) as recorded_at
    from source
)

select *
from extracted
where route_id = '102'