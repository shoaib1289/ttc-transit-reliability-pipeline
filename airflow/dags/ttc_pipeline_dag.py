"""TTC pipeline DAG: load snapshots -> dbt run -> dbt test.
Orchestrates the transformation pipeline on the mounted project."""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

# where the project is mounted inside the container
PROJECT = "/opt/airflow/ttc-project"
DBT = f"{PROJECT}/ttc"          # dbt project folder
PROFILES = DBT                   # profiles.yml lives here too

default_args = {
    "owner": "shoaib",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="ttc_reliability_pipeline",
    default_args=default_args,
    description="Load TTC GPS snapshots, transform with dbt, run data-quality tests",
    schedule_interval="@daily",       # would run once a day
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["ttc", "dbt", "duckdb"],
) as dag:

    # Step 1: load raw GPS snapshots into DuckDB
    load_snapshots = BashOperator(
        task_id="load_snapshots",
        bash_command=f"cd {PROJECT} && python scripts/load_rt_snapshots.py",
    )

    # Step 2: run dbt models (staging -> intermediate -> marts)
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {DBT} && python -m dbt.cli.main run "
            f"--profiles-dir {PROFILES} --project-dir {DBT}"
        ),
    )

    # Step 3: run dbt data-quality tests
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT} && python -m dbt.cli.main test "
            f"--profiles-dir {PROFILES} --project-dir {DBT}"
        ),
    )

    # define the order: load -> run -> test
    load_snapshots >> dbt_run >> dbt_test