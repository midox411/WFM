import os

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MLFLOW_EXPERIMENT = "wfm_attrition"

# Fixed point in time used to compute every agent's tenure, uniformly - never
# use termination_date for this (that would leak the label into the feature).
REFERENCE_DATE = "2026-07-31"

TEST_FRACTION = 0.15
VAL_FRACTION = 0.15  # taken out of the same pool, remaining ~0.70 is train
CV_FOLDS = 5
RANDOM_SEED = 42

PARAM_GRID = [
    {"max_depth": d, "n_estimators": n, "learning_rate": lr}
    for d in [2, 3, 4]
    for n in [50, 100]
    for lr in [0.05, 0.1]
]

THRESHOLD_SEARCH_RANGE = (0.1, 0.9, 0.05)  # (start, stop, step)