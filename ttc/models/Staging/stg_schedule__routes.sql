with source as (
    select * from {{ source('ttc_raw', 'raw_static_routes') }}
)

select
    route_id,
    route_short_name,
    route_long_name
from source