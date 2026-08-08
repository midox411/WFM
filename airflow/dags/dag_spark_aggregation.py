from __future__ import annotations

import sys
from datetime import datetime

from airflow.decorators import dag, task

SPARK_JOBS_DIR = "/opt/airflow/spark_jobs"
INPUT_PATH = "/opt/wfm_data/raw/call_events.parquet"
OUTPUT_DIR = "/opt/wfm_data/processed"
SPARK_MASTER = "spark://spark-master:7077"


@dag(
    dag_id="dag_spark_aggregation",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["wfm", "spark", "aggregation"],
)
def dag_spark_aggregation():

    @task
    def run_spark_job():
        if SPARK_JOBS_DIR not in sys.path:
            sys.path.insert(0, SPARK_JOBS_DIR)
        from aggregate_call_volumes import run_aggregation
        from pyspark.sql import SparkSession

        spark = (
            SparkSession.builder
            .appName("wfm_call_volume_aggregation")
            .master(SPARK_MASTER)
            .config("spark.executor.memory", "1g")
            .config("spark.driver.memory", "1g")
            .getOrCreate()
        )
        try:
            run_aggregation(spark, INPUT_PATH, OUTPUT_DIR)
        finally:
            spark.stop()

    run_spark_job()


dag_spark_aggregation()