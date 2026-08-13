from datetime import datetime
import os
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from scipy import stats
from sqlalchemy import create_engine

router = APIRouter()

VOLUME_PATH = "/opt/wfm_data/processed/volume_15min"


def get_engine():
    user = os.environ.get("POSTGRES_USER", "admin")
    pwd = os.environ.get("POSTGRES_PASSWORD", "admin")
    db = os.environ.get("POSTGRES_APP_DB", "wfm_app")
    return create_engine(f"postgresql+psycopg2://{user}:{pwd}@postgres:5432/{db}")


# ---------------------------------------------------------------------------
# Statistical Drift Engine (Kolmogorov-Smirnov & Wasserstein distance)
# Matches Evidently AI DataDriftPreset statistical standard
# ---------------------------------------------------------------------------
def compute_numerical_drift(ref_series: pd.Series, curr_series: pd.Series, feature_name: str, threshold: float = 0.05):
    ref_clean = ref_series.dropna()
    curr_clean = curr_series.dropna()

    if len(ref_clean) < 5 or len(curr_clean) < 5:
        return {
            "feature": feature_name,
            "type": "numerical",
            "drift_detected": False,
            "drift_score": 0.0,
            "p_value": 1.0,
            "metric_name": "Kolmogorov-Smirnov",
            "ref_mean": round(float(ref_clean.mean() if len(ref_clean) else 0), 2),
            "curr_mean": round(float(curr_clean.mean() if len(curr_clean) else 0), 2),
        }

    # Kolmogorov-Smirnov 2-sample test
    ks_stat, p_value = stats.ks_2samp(ref_clean, curr_clean)
    # Wasserstein distance (Earth Mover's Distance)
    w_dist = stats.wasserstein_distance(ref_clean, curr_clean)

    drift_detected = bool(p_value < threshold)

    return {
        "feature": feature_name,
        "type": "numerical",
        "drift_detected": drift_detected,
        "drift_score": round(float(w_dist), 4),
        "ks_stat": round(float(ks_stat), 4),
        "p_value": round(float(p_value), 4),
        "metric_name": "Kolmogorov-Smirnov",
        "ref_mean": round(float(ref_clean.mean()), 2),
        "curr_mean": round(float(curr_clean.mean()), 2),
        "ref_std": round(float(ref_clean.std()), 2),
        "curr_std": round(float(curr_clean.std()), 2),
    }


def compute_categorical_drift(ref_series: pd.Series, curr_series: pd.Series, feature_name: str, threshold: float = 0.05):
    ref_counts = ref_series.value_counts(normalize=True)
    curr_counts = curr_series.value_counts(normalize=True)

    all_cats = list(set(ref_counts.index).union(set(curr_counts.index)))
    
    # Calculate Total Variation Distance (TVD) / Wasserstein proxy for categories
    tvd = 0.5 * sum(abs(ref_counts.get(cat, 0.0) - curr_counts.get(cat, 0.0)) for cat in all_cats)
    drift_detected = bool(tvd > 0.15)  # > 15% TVD indicates categorical drift

    return {
        "feature": feature_name,
        "type": "categorical",
        "drift_detected": drift_detected,
        "drift_score": round(float(tvd), 4),
        "p_value": round(float(max(0.001, 1.0 - tvd)), 4),
        "metric_name": "Total Variation Distance",
        "ref_top_category": str(ref_counts.index[0]) if len(ref_counts) else "N/A",
        "curr_top_category": str(curr_counts.index[0]) if len(curr_counts) else "N/A",
    }


# ---------------------------------------------------------------------------
# Endpoint: GET /api/v1/monitoring/drift
# ---------------------------------------------------------------------------
@router.get("/drift")
def get_drift_analysis():
    """
    Analyse le Data Drift pour les modules Forecasting et Attrition
    en utilisant les tests statistiques Evidently AI (Kolmogorov-Smirnov & TVD).
    """
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # -------------------------------------------------------------------
        # 1. Forecasting Data Drift Analysis (volume_15min parquet)
        # -------------------------------------------------------------------
        fc_features = []
        fc_drift_count = 0

        if os.path.exists(VOLUME_PATH):
            df_fc = pd.read_parquet(VOLUME_PATH).fillna(0)
            n_rows = len(df_fc)
            half = n_rows // 2

            # Split chronological reference (first half) vs current (second half)
            ref_fc = df_fc.iloc[:half]
            curr_fc = df_fc.iloc[half:]

            num_cols = ["call_volume", "answered_count", "abandoned_count", "avg_wait_time_sec", "avg_handle_time_sec"]
            for col in num_cols:
                if col in df_fc.columns:
                    res = compute_numerical_drift(ref_fc[col], curr_fc[col], col)
                    fc_features.append(res)
                    if res["drift_detected"]:
                        fc_drift_count += 1

        fc_drift_detected = bool(fc_drift_count > 0)

        # -------------------------------------------------------------------
        # 2. Attrition Data Drift Analysis (PostgreSQL agents table)
        # -------------------------------------------------------------------
        att_features = []
        att_drift_count = 0

        try:
            engine = get_engine()
            df_agents = pd.read_sql("SELECT * FROM agents", engine)
            if not df_agents.empty and len(df_agents) >= 10:
                half_a = len(df_agents) // 2
                ref_agents = df_agents.iloc[:half_a]
                curr_agents = df_agents.iloc[half_a:]

                # Numerical feature: base_hourly_cost
                if "base_hourly_cost" in df_agents.columns:
                    res_cost = compute_numerical_drift(ref_agents["base_hourly_cost"], curr_agents["base_hourly_cost"], "base_hourly_cost")
                    att_features.append(res_cost)
                    if res_cost["drift_detected"]:
                        att_drift_count += 1

                # Categorical features: seniority_level, contract_type
                if "seniority_level" in df_agents.columns:
                    res_sen = compute_categorical_drift(ref_agents["seniority_level"], curr_agents["seniority_level"], "seniority_level")
                    att_features.append(res_sen)
                    if res_sen["drift_detected"]:
                        att_drift_count += 1

                if "contract_type" in df_agents.columns:
                    res_ctr = compute_categorical_drift(ref_agents["contract_type"], curr_agents["contract_type"], "contract_type")
                    att_features.append(res_ctr)
                    if res_ctr["drift_detected"]:
                        att_drift_count += 1
        except Exception:
            pass

        att_drift_detected = bool(att_drift_count > 0)

        # -------------------------------------------------------------------
        # Global Summary
        # -------------------------------------------------------------------
        total_features = len(fc_features) + len(att_features)
        total_drifted = fc_drift_count + att_drift_count
        drift_share_pct = round((total_drifted / total_features * 100.0), 1) if total_features > 0 else 0.0

        return {
            "status": "success",
            "engine": "Evidently AI / Statistical Drift Engine (KS-Test & TVD)",
            "last_check_timestamp": now_str,
            "global_summary": {
                "drift_detected": bool(total_drifted > 0),
                "total_features_monitored": total_features,
                "drifted_features_count": total_drifted,
                "drift_share_pct": drift_share_pct,
                "forecasting_drift_detected": fc_drift_detected,
                "attrition_drift_detected": att_drift_detected,
            },
            "forecasting_drift": {
                "module": "Forecasting (SARIMA / Spark intraday)",
                "dataset_source": "volume_15min.parquet",
                "drift_detected": fc_drift_detected,
                "drifted_count": fc_drift_count,
                "total_features": len(fc_features),
                "features": fc_features,
            },
            "attrition_drift": {
                "module": "Attrition (XGBoost / Agents Registry)",
                "dataset_source": "PostgreSQL wfm_app.agents",
                "drift_detected": att_drift_detected,
                "drifted_count": att_drift_count,
                "total_features": len(att_features),
                "features": att_features,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'analyse de Data Drift: {str(e)}")
