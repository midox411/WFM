from __future__ import annotations

import sys
from datetime import datetime

from airflow.decorators import dag, task

ATTRITION_DIR = "/opt/airflow/ml_attrition"


@dag(
    dag_id="dag_train_attrition",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["wfm", "ml", "attrition"],
)
def dag_train_attrition():

    @task
    def run_training():
        if ATTRITION_DIR not in sys.path:
            sys.path.insert(0, ATTRITION_DIR)
        import train_attrition
        model, test_metrics, threshold = train_attrition.run()
        print(f"Test metrics: {test_metrics} | decision threshold: {threshold}")

    run_training()


dag_train_attrition()