from __future__ import annotations

import sys
from datetime import datetime

from airflow.decorators import dag, task

FORECASTING_DIR = "/opt/airflow/ml_forecasting"


@dag(
    dag_id="dag_train_forecasting",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["wfm", "ml", "forecasting"],
)
def dag_train_forecasting():

    @task
    def run_training():
        if FORECASTING_DIR not in sys.path:
            sys.path.insert(0, FORECASTING_DIR)
        import train_forecast
        winner, test_metrics = train_forecast.run()
        print(f"Winning model: {winner} | test metrics: {test_metrics}")

    run_training()


dag_train_forecasting()