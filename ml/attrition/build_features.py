"""
Builds the per-agent feature table for the attrition model, reading from the
wfm_app Postgres database (loaded by dag_ingestion).

IMPORTANT - avoiding leakage: tenure is computed from a single FIXED reference
date for every agent (config.REFERENCE_DATE), never from termination_date.
Similarly, raw "days scheduled" is intentionally excluded from the feature set:
since our simulator stops generating shifts once an agent leaves, a raw count
of scheduled days is a near-direct proxy for "did this agent already leave" -
same leak category as an unguarded tenure calculation would be.
"""
import os
import pandas as pd
from sqlalchemy import create_engine

import config


def get_engine():
    user = os.environ["POSTGRES_USER"]
    pwd = os.environ["POSTGRES_PASSWORD"]
    db = os.environ.get("POSTGRES_APP_DB", "wfm_app")
    return create_engine(f"postgresql+psycopg2://{user}:{pwd}@postgres:5432/{db}")


def build_feature_table(engine):
    agents = pd.read_sql("SELECT * FROM agents", engine)
    skills_count = pd.read_sql(
        "SELECT agent_id, COUNT(*) AS n_skills FROM agent_skills GROUP BY agent_id", engine
    )
    shifts_count = pd.read_sql(
        "SELECT agent_id, COUNT(*) AS n_scheduled_days FROM agent_shifts GROUP BY agent_id", engine
    )
    absences_count = pd.read_sql(
        "SELECT agent_id, COUNT(*) AS n_absences FROM agent_absences GROUP BY agent_id", engine
    )
    call_stats = pd.read_sql("""
        SELECT agent_id,
               COUNT(*) AS n_calls_handled,
               AVG(handle_time_sec) AS avg_handle_time_sec,
               AVG(wait_time_sec) AS avg_wait_time_sec
        FROM call_events
        WHERE agent_id IS NOT NULL
        GROUP BY agent_id
    """, engine)

    df = agents.merge(skills_count, on="agent_id", how="left")
    df = df.merge(shifts_count, on="agent_id", how="left")  # kept only to compute rates below
    df = df.merge(absences_count, on="agent_id", how="left")
    df = df.merge(call_stats, on="agent_id", how="left")

    for c in ["n_skills", "n_scheduled_days", "n_absences", "n_calls_handled"]:
        df[c] = df[c].fillna(0)
    df["avg_handle_time_sec"] = df["avg_handle_time_sec"].fillna(df["avg_handle_time_sec"].median())
    df["avg_wait_time_sec"] = df["avg_wait_time_sec"].fillna(df["avg_wait_time_sec"].median())

    df["hire_date"] = pd.to_datetime(df["hire_date"])
    reference_date = pd.Timestamp(config.REFERENCE_DATE)
    df["tenure_days"] = (reference_date - df["hire_date"]).dt.days

    # rates, not raw counts - normalized by each agent's own exposure so a
    # short (censored) tenure doesn't mechanically produce a "low count" that
    # the model could use as a leaky proxy for the label
    df["absence_rate"] = df["n_absences"] / df["n_scheduled_days"].replace(0, 1)
    df["calls_per_scheduled_day"] = df["n_calls_handled"] / df["n_scheduled_days"].replace(0, 1)

    df["is_terminated"] = (df["status"] == "terminated").astype(int)

    cat_cols = ["team", "seniority_level", "contract_type"]
    df = pd.get_dummies(df, columns=cat_cols, drop_first=True)
    dummy_cols = [c for c in df.columns if c.startswith(tuple(f"{c0}_" for c0 in cat_cols))]

    feature_cols = [
        "tenure_days", "n_skills", "absence_rate", "calls_per_scheduled_day",
        "avg_handle_time_sec", "avg_wait_time_sec", "base_hourly_cost",
    ] + dummy_cols

    X = df[feature_cols].copy()
    y = df["is_terminated"]
    agent_ids = df["agent_id"]
    return X, y, agent_ids


if __name__ == "__main__":
    engine = get_engine()
    X, y, agent_ids = build_feature_table(engine)
    print(f"Features: {X.shape} | positives: {y.sum()} / {len(y)} ({y.mean()*100:.1f}%)")
    print(X.head())