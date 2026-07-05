{% snapshot schedule_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='trip_id || stop_id',
      strategy='check',
      check_cols=['scheduled_arrival_str']
    )
}}

select
    trip_id,
    stop_id,
    scheduled_arrival_str,
    stop_sequence
from {{ ref('stg_schedule__stop_times') }}

{% endsnapshot %}