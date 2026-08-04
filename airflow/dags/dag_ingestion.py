"""
dag_ingestion

Runs the synthetic data simulator once (or on manual trigger), uploads the raw
Parquet files to MinIO (data lake, bucket 'wfm-datalake'), then loads them into
the 'wfm_app' PostgreSQL database.

In a real production setting, this DAG would instead pull daily exports from
Five9/CRM. Here it plays that role using simulated data so the rest of the
pipeline (Spark aggregation, forecasting, attrition, scheduling) can be built
and tested end-to-end.

Note on call_events volume (~3.5M rows): loaded via SQLAlchemy chunked
to_sql for simplicity. If this becomes a bottleneck, switch to Postgres COPY
(psycopg2 copy_expert) instead - flagged here for later optimization.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
from airflow.decorators import dag, task
from airflow.hooks.base import BaseHook
from sqlalchemy import create_engine

# The simulator package lives outside the Airflow DAGs folder; make it importable.
SIMULATOR_DIR = "/opt/airflow/data_simulator"
if SIMULATOR_DIR not in sys.path:
    sys.path.insert(0, SIMULATOR_DIR)

RAW_DATA_DIR = Path("/opt/airflow/data_raw")

MINIO_ENDPOINT = "http://minio:9000"
MINIO_BUCKET = "wfm-datalake"

POSTGRES_CONN = "postgresql+psycopg2://{user}:{pwd}@postgres:5432/{db}"

TABLES = [
    "skills",
    "agents",
    "agent_skills",
    "agent_shifts",
    "agent_breaks",
    "agent_absences",
    "call_events",
]


def _pg_engine():
    import os
    user = os.environ["POSTGRES_USER"]
    pwd = os.environ["POSTGRES_PASSWORD"]
    db = os.environ.get("POSTGRES_APP_DB", "wfm_app")
    return create_engine(POSTGRES_CONN.format(user=user, pwd=pwd, db=db))


def _minio_client():
    import os
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    )


@dag(
    dag_id="dag_ingestion",
    schedule=None,  # triggered manually for now; move to @daily once this mimics a real feed
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["wfm", "ingestion", "simulation"],
)
def dag_ingestion():

    @task
    def generate_data() -> str:
        """Runs the simulator and writes Parquet files to RAW_DATA_DIR."""
        import run_all  # from the simulator package
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        run_all.run(output_dir=RAW_DATA_DIR)
        return str(RAW_DATA_DIR)

    @task
    def upload_to_minio(raw_dir: str) -> str:
        client = _minio_client()
        for table in TABLES:
            local_path = Path(raw_dir) / f"{table}.parquet"
            key = f"raw/{table}.parquet"
            client.upload_file(str(local_path), MINIO_BUCKET, key)
            print(f"Uploaded {local_path} -> s3://{MINIO_BUCKET}/{key}")
        return raw_dir

    @task
    def load_to_postgres(raw_dir: str) -> None:
        engine = _pg_engine()
        for table in TABLES:
            local_path = Path(raw_dir) / f"{table}.parquet"
            df = pd.read_parquet(local_path)
            # replace on each run: simulator output is deterministic (fixed seed),
            # so re-running regenerates the same reference dataset from scratch
            df.to_sql(
                table,
                engine,
                if_exists="replace",
                index=False,
                chunksize=50_000,
                method="multi",
            )
            print(f"Loaded {len(df):,} rows into wfm_app.{table}")

    raw_dir = generate_data()
    uploaded = upload_to_minio(raw_dir)
    load_to_postgres(uploaded)


dag_ingestion()