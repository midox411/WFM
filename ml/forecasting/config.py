import os

# Where Spark wrote the aggregated tables (see spark_jobs/aggregate_call_volumes.py)
PROCESSED_DIR = "/opt/wfm_data/processed"
DAILY_VOLUME_PATH = f"{PROCESSED_DIR}/volume_daily"

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MLFLOW_EXPERIMENT = "wfm_forecasting"

TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15  # remaining 0.15 is the held-out test set

WALK_FORWARD_HORIZON = 7  # days per fold

# Same calendar used by the simulator (data/simulator/config.py) so Prophet can
# use it as a holiday regressor - duplicated here to keep ml/ independent from
# the simulator package.
HOLIDAYS = [
    "2025-08-14", "2025-08-20", "2025-08-21", "2025-09-05",
    "2025-11-06", "2025-11-18",
    "2026-01-01", "2026-01-11", "2026-01-14",
    "2026-03-20", "2026-03-21",
    "2026-05-01", "2026-05-27", "2026-06-17", "2026-07-30",
]