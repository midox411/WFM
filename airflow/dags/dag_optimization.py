from __future__ import annotations

import sys
from datetime import datetime

from airflow.decorators import dag, task

OPTIMIZATION_DIR = "/opt/airflow/ml_optimization"


@dag(
    dag_id="dag_optimization",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["wfm", "ml", "optimization"],
)
def dag_optimization():

    @task
    def run_optimization():
        if OPTIMIZATION_DIR not in sys.path:
            sys.path.insert(0, OPTIMIZATION_DIR)
        import run_optimization
        result = run_optimization.run()
        if result:
            print(
                f"Optimization done | status={result['solver_status']} "
                f"| coverage={result['coverage_rate']*100:.1f}% "
                f"| cost saving={result['cost_saving_pct']:.1f}%"
            )

    run_optimization()


dag_optimization()