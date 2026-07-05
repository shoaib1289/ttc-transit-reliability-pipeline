-- The "promise": scheduled arrival time for each trip at each stop.
with source as (
    select * from {{ source('ttc_raw', 'raw_static_stop_times') }}
)

select
    trip_id,
    stop_id,
    cast(stop_sequence as integer)        as stop_sequence,
    arrival_time                          as scheduled_arrival_str,  -- keep raw string for now
    departure_time                        as scheduled_departure_str
from source