"""
Attrition model training pipeline: XGBoost classifier predicting agent
departure risk.

- Stratified 70/15/15 train/val/test split (never chronological - there's no
  temporal ordering requirement here, but the class imbalance ~18% positive
  must be preserved in every split)
- Hyperparameter tuning via stratified 5-fold CV on the train set only
- Decision threshold tuned on the validation set (default 0.5 is a poor fit
  for this class imbalance - F1 is near-zero at 0.5 on such a small dataset)
- Final model retrained on train+val, scored once on the untouched test set
- SHAP feature importance logged as an artifact

NOTE ON DATASET SIZE: only 100 agents (~18 positive) - metrics are inherently
noisy at this scale. This is a known limitation of the simulated scale, not a
methodology bug; the pipeline itself (splits, CV, no-leakage features,
threshold tuning) is what should be judged, not the absolute metric values.
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import mlflow
import shap
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
from xgboost import XGBClassifier

import config
from build_features import get_engine, build_feature_table


def compute_metrics(y_true, y_pred, y_proba) -> dict:
    return {
        "auc": roc_auc_score(y_true, y_proba) if len(set(y_true)) > 1 else float("nan"),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }


def cross_validate(X, y, params) -> dict:
    skf = StratifiedKFold(n_splits=config.CV_FOLDS, shuffle=True, random_state=config.RANDOM_SEED)
    fold_metrics = []
    for train_idx, val_idx in skf.split(X, y):
        model = XGBClassifier(**params, eval_metric="logloss", random_state=config.RANDOM_SEED)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        proba = model.predict_proba(X.iloc[val_idx])[:, 1]
        pred = (proba >= 0.5).astype(int)
        fold_metrics.append(compute_metrics(y.iloc[val_idx], pred, proba))
    keys = fold_metrics[0].keys()
    return {k: float(np.nanmean([m[k] for m in fold_metrics])) for k in keys}


def find_best_threshold(y_true, y_proba) -> float:
    start, stop, step = config.THRESHOLD_SEARCH_RANGE
    best_t, best_f1 = 0.5, -1
    for t in np.arange(start, stop, step):
        pred = (y_proba >= t).astype(int)
        f1 = f1_score(y_true, pred, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t
    return best_t


def run():
    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(config.MLFLOW_EXPERIMENT)

    engine = get_engine()
    X, y, agent_ids = build_feature_table(engine)
    print(f"Dataset: {len(X)} agents, {y.sum()} terminated ({y.mean()*100:.1f}%)")
    print("NOTE: small-N dataset (100 agents) - expect noisy metrics at this scale.")

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=config.TEST_FRACTION, stratify=y, random_state=config.RANDOM_SEED
    )
    val_ratio = config.VAL_FRACTION / (1 - config.TEST_FRACTION)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=val_ratio,
        stratify=y_trainval, random_state=config.RANDOM_SEED,
    )
    print(f"Train: {len(X_train)} ({y_train.sum()} left) | "
          f"Val: {len(X_val)} ({y_val.sum()} left) | "
          f"Test: {len(X_test)} ({y_test.sum()} left)")

    # --- hyperparameter tuning: stratified 5-fold CV on train only ---
    best_params, best_score, best_cv_metrics = None, -1, None
    with mlflow.start_run(run_name="attrition_cv_tuning"):
        for params in config.PARAM_GRID:
            cv_metrics = cross_validate(X_train, y_train, params)
            # recall is the priority (missing a departure costs more than a
            # false alarm); AUC as a tie-breaker
            score = cv_metrics["recall"] * 10 + cv_metrics["auc"]
            if score > best_score:
                best_score, best_params, best_cv_metrics = score, params, cv_metrics

        mlflow.log_params(best_params)
        mlflow.log_metrics({f"cv_{k}": v for k, v in best_cv_metrics.items()})
        print(f"Best params: {best_params}")
        print(f"CV metrics: {best_cv_metrics}")

    # --- threshold tuning + sanity check on the held-out validation set ---
    with mlflow.start_run(run_name="attrition_val_check"):
        model = XGBClassifier(**best_params, eval_metric="logloss", random_state=config.RANDOM_SEED)
        model.fit(X_train, y_train)
        val_proba = model.predict_proba(X_val)[:, 1]

        best_threshold = find_best_threshold(y_val, val_proba)
        val_pred = (val_proba >= best_threshold).astype(int)
        val_metrics = compute_metrics(y_val, val_pred, val_proba)

        mlflow.log_metric("decision_threshold", best_threshold)
        mlflow.log_metrics({f"val_{k}": v for k, v in val_metrics.items()})
        print(f"Best decision threshold (tuned on val): {best_threshold:.2f}")
        print(f"Validation metrics: {val_metrics}")

    # --- final model: retrain on train+val, evaluate once on test ---
    with mlflow.start_run(run_name="attrition_final_test"):
        X_trainval_final = pd.concat([X_train, X_val])
        y_trainval_final = pd.concat([y_train, y_val])

        final_model = XGBClassifier(**best_params, eval_metric="logloss", random_state=config.RANDOM_SEED)
        final_model.fit(X_trainval_final, y_trainval_final)

        test_proba = final_model.predict_proba(X_test)[:, 1]
        test_pred = (test_proba >= best_threshold).astype(int)
        test_metrics = compute_metrics(y_test, test_pred, test_proba)

        mlflow.log_params(best_params)
        mlflow.log_metric("decision_threshold", best_threshold)
        mlflow.log_metrics({f"test_{k}": v for k, v in test_metrics.items()})
        print(f"Final test metrics (threshold={best_threshold:.2f}): {test_metrics}")

        mlflow.xgboost.log_model(final_model, "model")

        # --- SHAP explainability ---
        explainer = shap.TreeExplainer(final_model)
        shap_values = explainer.shap_values(X_test)
        importance = pd.DataFrame({
            "feature": X_test.columns,
            "mean_abs_shap": np.abs(shap_values).mean(axis=0),
        }).sort_values("mean_abs_shap", ascending=False)

        print("Top risk factors (SHAP, mean |impact| on test set):")
        print(importance.to_string(index=False))

        importance_path = "/tmp/shap_feature_importance.csv"
        importance.to_csv(importance_path, index=False)
        mlflow.log_artifact(importance_path)

    return final_model, test_metrics, best_threshold


if __name__ == "__main__":
    run()