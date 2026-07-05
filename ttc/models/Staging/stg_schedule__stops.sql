-- Stop locations — the coordinates we match bus GPS against.
with source as (
    select * from {{ source('ttc_raw', 'raw_static_stops') }}
)

select
    stop_id,
    stop_name,
    cast(stop_lat as double)              as stop_latitude,
    cast(stop_lon as double)              as stop_longitude
from source