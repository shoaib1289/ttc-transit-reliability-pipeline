with source as (
    select * from {{ source('ttc_raw', 'raw_static_trips') }}
)

select
    trip_id,
    route_id,
    service_id,
    trip_headsign,
    cast(direction_id as integer) as direction_id
from source