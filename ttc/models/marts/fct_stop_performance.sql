{{ config(materialized='incremental', unique_key='trip_stop_id') }}

with actual as (
    select
        vehicle_id, stop_id, stop_name, actual_arrival,
        extract(hour from actual_arrival) * 3600
          + extract(minute from actual_arrival) * 60
          + extract(second from actual_arrival) as actual_secs
    from {{ ref('int_actual_arrivals') }}
),

scheduled as (
    select
        st.stop_id, st.scheduled_arrival_str, t.direction_id, t.trip_headsign,
        cast(split_part(st.scheduled_arrival_str, ':', 1) as integer) * 3600
          + cast(split_part(st.scheduled_arrival_str, ':', 2) as integer) * 60
          + cast(split_part(st.scheduled_arrival_str, ':', 3) as integer) as sched_secs
    from {{ ref('stg_schedule__stop_times') }} st
    join {{ ref('stg_schedule__trips') }} t on st.trip_id = t.trip_id
    where t.route_id = '102'
),

matched as (
    select
        a.vehicle_id, a.stop_id, a.stop_name, a.actual_arrival, a.actual_secs,
        s.scheduled_arrival_str, s.sched_secs, s.direction_id, s.trip_headsign,
        row_number() over (
            partition by a.vehicle_id, a.stop_id, a.actual_arrival
            order by abs(a.actual_secs - s.sched_secs)
        ) as rn
    from actual a
    join scheduled s on a.stop_id = s.stop_id
),

final as (
    select
        a.vehicle_id || '-' || a.stop_id || '-' || cast(a.actual_arrival as varchar) as trip_stop_id,
        vehicle_id, stop_id, stop_name, actual_arrival,
        scheduled_arrival_str, direction_id, trip_headsign,
        (actual_secs - sched_secs) as delay_seconds,
        round((actual_secs - sched_secs) / 60.0, 1) as delay_minutes
    from matched a
    where rn = 1
      and abs(actual_secs - sched_secs) <= 1800
)

select * from final
{% if is_incremental() %}
  where actual_arrival > (select max(actual_arrival) from {{ this }})
{% endif %}