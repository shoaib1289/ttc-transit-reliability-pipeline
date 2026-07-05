with performance as (
    select * from {{ ref('fct_stop_performance') }}
),

flagged as (
    select
        stop_name,
        direction_id,
        delay_minutes,
        case when delay_minutes between -1 and 5 then 1 else 0 end as is_on_time
    from performance
)

select
    stop_name,
    direction_id,
    count(*)                                     as total_arrivals,
    round(avg(delay_minutes), 2)                 as avg_delay_min,
    round(min(delay_minutes), 2)                 as earliest_min,
    round(max(delay_minutes), 2)                 as latest_min,
    sum(is_on_time)                              as on_time_count,
    round(100.0 * sum(is_on_time) / count(*), 1) as on_time_pct
from flagged
group by stop_name, direction_id
order by stop_name, direction_id