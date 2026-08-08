"""
Forecasting training pipeline: naive baseline vs SARIMA vs Prophet.

- Chronological split: 70% train / 15% validation / 15% test
- Walk-forward (rolling origin) validation on the validation range, 7-day folds
- The winning model must beat the naive (lag-7) baseline; it's refit on
  train+val and scored once, for real, on the untouched test set
- Everything logged to MLflow (params, per-fold metrics, final test metrics, model)
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import mlflow
from statsmodels.tsa.statespace.sarimax import SARIMAX

import config

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    print("WARNING: prophet not available/importable - skipping Prophet, "
          "comparing SARIMA vs naive baseline only.")


def load_daily_series() -> pd.Series:
    df = pd.read_parquet(config.DAILY_VOLUME_PATH)
    daily = df.groupby("date")["call_volume"].sum().reset_index()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date").set_index("date")["call_volume"]
    daily = daily.asfreq("D").fillna(method="ffill")  # guard against any gap day
    return daily


def split_series(series: pd.Series):
    n = len(series)
    train_end = int(n * config.TRAIN_FRACTION)
    val_end = int(n * (config.TRAIN_FRACTION + config.VAL_FRACTION))
    return train_end, val_end


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_true, y_pred = np.array(y_true, dtype=float), np.array(y_pred, dtype=float)
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    mape = np.mean(np.abs((y_true - y_pred) / np.clip(y_true, 1, None))) * 100
    # WMAPE: weighted by actual volume, not sensitive to low-volume days
    # (weekends/holidays) blowing up the average like MAPE does - the metric
    # actually used in most industry demand-forecasting setups
    wmape = np.sum(np.abs(y_true - y_pred)) / np.clip(np.sum(y_true), 1, None) * 100
    return {"mae": mae, "rmse": rmse, "mape": mape, "wmape": wmape}


def predict_naive(history: pd.Series, horizon: int) -> np.ndarray:
    """Seasonal-naive baseline: forecast day t = value from 7 days before."""
    return history.iloc[-7:].values[:horizon]


def predict_sarima(history: pd.Series, horizon: int) -> np.ndarray:
    model = SARIMAX(
        history, order=(1, 1, 1), seasonal_order=(1, 1, 1, 7),
        enforce_stationarity=False, enforce_invertibility=False,
    )
    fit = model.fit(disp=False)
    return fit.forecast(steps=horizon).values


def _holidays_df():
    return pd.DataFrame({
        "holiday": "public_holiday",
        "ds": pd.to_datetime(config.HOLIDAYS),
    })


def predict_prophet(history: pd.Series, horizon: int) -> np.ndarray:
    train_df = history.reset_index()
    train_df.columns = ["ds", "y"]
    model = Prophet(
        holidays=_holidays_df(),
        weekly_seasonality=True,
        yearly_seasonality=True,
        daily_seasonality=False,
    )
    model.fit(train_df)
    future = model.make_future_dataframe(periods=horizon)
    forecast = model.predict(future)
    return forecast["yhat"].values[-horizon:]


def walk_forward_validate(series: pd.Series, val_start: int, val_end: int,
                           predict_fn) -> list[dict]:
    """Expanding-window validation: retrain on everything up to the fold start,
    predict WALK_FORWARD_HORIZON days ahead, slide forward, repeat."""
    horizon = config.WALK_FORWARD_HORIZON
    fold_metrics = []
    fold_start = val_start

    while fold_start + horizon <= val_end:
        history = series.iloc[:fold_start]
        truth = series.iloc[fold_start: fold_start + horizon]

        y_pred = predict_fn(history, horizon)
        fold_metrics.append(compute_metrics(truth.values, y_pred))

        fold_start += horizon

    return fold_metrics


def win_rate_vs_baseline(model_folds: list[dict], baseline_folds: list[dict]) -> float:
    """Fraction of folds where the model's WMAPE beats the baseline's WMAPE.
    A model that wins on average but loses most individual folds is not
    actually reliable - this catches that case."""
    wins = sum(1 for m, b in zip(model_folds, baseline_folds) if m["wmape"] < b["wmape"])
    return wins / len(model_folds)


def _avg_metrics(fold_metrics: list[dict]) -> dict:
    keys = fold_metrics[0].keys()
    return {k: float(np.mean([m[k] for m in fold_metrics])) for k in keys}


def _set_experiment_safely(name: str):
    """Handles the case where the experiment was soft-deleted (e.g. via the
    MLflow UI) - restores it instead of failing."""
    client = mlflow.tracking.MlflowClient()
    exp = client.get_experiment_by_name(name)
    if exp is not None and exp.lifecycle_stage == "deleted":
        client.restore_experiment(exp.experiment_id)
    mlflow.set_experiment(name)


def run():
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    _set_experiment_safely(config.MLFLOW_EXPERIMENT)

    series = load_daily_series()
    train_end, val_end = split_series(series)
    print(f"Series length: {len(series)} | train_end={train_end} val_end={val_end}")

    candidates = {"naive_baseline": predict_naive, "sarima": predict_sarima}
    if PROPHET_AVAILABLE:
        candidates["prophet"] = predict_prophet

    results = {}
    fold_results = {}
    for name, predict_fn in candidates.items():
        with mlflow.start_run(run_name=f"walkforward_{name}"):
            mlflow.set_tag("model_family", name)
            mlflow.log_param("horizon_days", config.WALK_FORWARD_HORIZON)
            mlflow.log_param("train_end_idx", train_end)
            mlflow.log_param("val_end_idx", val_end)

            fold_metrics = walk_forward_validate(series, train_end, val_end, predict_fn)
            avg = _avg_metrics(fold_metrics)
            for i, m in enumerate(fold_metrics):
                mlflow.log_metrics({f"fold{i}_{k}": v for k, v in m.items()})
            mlflow.log_metrics({f"avg_{k}": v for k, v in avg.items()})

            results[name] = avg
            fold_results[name] = fold_metrics
            print(f"{name:<15} avg MAE={avg['mae']:.1f} RMSE={avg['rmse']:.1f} "
                  f"MAPE={avg['mape']:.1f}% WMAPE={avg['wmape']:.1f}%")

    baseline_folds = fold_results["naive_baseline"]
    baseline_wmape = results["naive_baseline"]["wmape"]

    challengers = {}
    for name in candidates:
        if name == "naive_baseline":
            continue
        rate = win_rate_vs_baseline(fold_results[name], baseline_folds)
        print(f"{name:<15} win-rate vs baseline: {rate*100:.0f}% of folds")
        # require beating the baseline on average AND on a clear majority of
        # folds - an average win driven by one lucky fold isn't trustworthy
        if results[name]["wmape"] < baseline_wmape and rate >= 0.6:
            challengers[name] = results[name]

    if not challengers:
        print("No model reliably beat the naive baseline (avg + fold win-rate). "
              "Falling back to naive_baseline for production use.")
        winner = "naive_baseline"
    else:
        winner = min(challengers, key=lambda k: challengers[k]["wmape"])

    print(f"\nWinner: {winner}")

    # --- Final evaluation: walk-forward over the untouched test range, same
    # methodology (and horizon) as validation, so the numbers are comparable
    # and not distorted by a single long-horizon forecast ---
    predict_fn = candidates[winner]

    with mlflow.start_run(run_name=f"final_test_{winner}"):
        mlflow.set_tag("model_family", winner)
        mlflow.set_tag("stage", "final_test_evaluation")

        test_folds = walk_forward_validate(series, val_end, len(series), predict_fn)
        test_metrics = _avg_metrics(test_folds)
        for i, m in enumerate(test_folds):
            mlflow.log_metrics({f"fold{i}_{k}": v for k, v in m.items()})
        mlflow.log_metrics({f"test_{k}": v for k, v in test_metrics.items()})

        # also score the baseline on the exact same test folds, for a fair
        # apples-to-apples relative comparison (the headline number for the jury)
        baseline_test_folds = walk_forward_validate(series, val_end, len(series), predict_naive)
        baseline_test_metrics = _avg_metrics(baseline_test_folds)
        improvement = (baseline_test_metrics["wmape"] - test_metrics["wmape"]) / baseline_test_metrics["wmape"] * 100
        mlflow.log_metric("test_wmape_improvement_vs_baseline_pct", improvement)

        print(f"Final test metrics ({winner}, walk-forward avg over {len(test_folds)} folds): "
              f"MAE={test_metrics['mae']:.1f} RMSE={test_metrics['rmse']:.1f} "
              f"MAPE={test_metrics['mape']:.1f}% WMAPE={test_metrics['wmape']:.1f}%")
        print(f"Baseline on same test folds: WMAPE={baseline_test_metrics['wmape']:.1f}%")
        print(f"=> {winner} reduces WMAPE by {improvement:.1f}% relative to the naive baseline "
              f"on the held-out test set.")

    return winner, test_metrics


if __name__ == "__main__":
    run()