# WFM Intelligence Platform

An end-to-end workforce management platform combining demand forecasting, schedule optimization, and attrition risk prediction, built as a large-scale data science / ML engineering project (Master's project — Big Data & Cloud Computing).

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Repository structure](#repository-structure)
- [Getting started](#getting-started)
- [Modules](#modules)
- [Model training, validation & testing](#model-training-validation--testing)
- [Testing strategy](#testing-strategy)
- [Roadmap](#roadmap)

## Overview

Workforce management in call centers / operations teams typically involves three problems handled in isolation:

1. **Forecasting** incoming demand (call/ticket volume)
2. **Scheduling** staff accordingly
3. **Anticipating** agent attrition (turnover, burnout)

This project unifies all three into a single data-driven platform, with a "what-if" simulator to test staffing decisions before applying them. Since production data from a real call center isn't available, a realistic synthetic data generator drives the whole pipeline at scale.

## Architecture

```
                     ┌─────────────────────────────────────────┐
                     │              DATA SOURCES                │
                     │   Synthetic event simulator (Poisson)     │
                     └───────────────────┬───────────────────────┘
                                          │
                              ┌───────────▼───────────┐
                              │   Apache Airflow (DAGs) │
                              │   ETL orchestration     │
                              └───────────┬───────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
             ┌──────▼──────┐      ┌───────▼───────┐     ┌───────▼───────┐
             │ Apache Spark │      │  PostgreSQL   │     │  MinIO (S3)   │
             │ (aggregation)│      │ (app data)    │     │ (raw data lake)│
             └──────┬──────┘      └───────┬───────┘     └───────────────┘
                    │                     │
        ┌───────────┴─────────────────────┴───────────┐
        │                 ML LAYER                      │
        │  Forecasting │ Optimization │ Attrition risk  │
        │        (tracked via MLflow)                    │
        └───────────────────┬───────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  FastAPI (API)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    Dashboard    │
                    └─────────────────┘

        Cross-cutting: Evidently AI (drift monitoring), Docker Compose (all services)
```

## Tech stack

| Layer | Tools |
|---|---|
| Data simulation | Python, Faker, non-homogeneous Poisson process |
| Storage | PostgreSQL, MinIO (S3-compatible object storage) |
| Big data processing | Apache Spark, Apache Airflow |
| Forecasting | Prophet, statsmodels (SARIMA), PyTorch (LSTM / Temporal Fusion Transformer) |
| Optimization | OR-Tools / PuLP (linear programming), Erlang C staffing model |
| Attrition model | scikit-learn, XGBoost, SHAP, lifelines (survival analysis) |
| MLOps | MLflow (tracking + registry), Evidently AI (drift detection) |
| Backend | FastAPI, Pydantic |
| Frontend | Streamlit (MVP) or React + Recharts (target) |
| Infrastructure | Docker, Docker Compose |

## Repository structure

```
wfm-platform/
├── docker-compose.yml
├── .env.example
├── docker/                 # custom Dockerfiles (airflow, mlflow)
├── init-scripts/postgres/  # multi-database init script
├── airflow/dags/           # Airflow DAGs
├── data/                   # simulator, raw, processed (gitignored)
├── ml/
│   ├── forecasting/        # Prophet / SARIMA / LSTM training & evaluation
│   ├── attrition/          # XGBoost training, SHAP explainability
│   ├── optimization/       # Erlang C + OR-Tools scheduler
│   └── common/             # shared utilities (data validation, MLflow helpers)
├── spark_jobs/             # PySpark aggregation jobs
├── api/                    # FastAPI app
├── monitoring/             # Evidently AI drift reports
├── frontend/               # dashboard app
└── tests/
```

## Getting started

### Prerequisites

- Docker Desktop installed and running

### Setup

```bash
git clone https://github.com/midox411/WFM.git
cd WFM
cp .env.example .env
# edit .env: set your own POSTGRES_PASSWORD and MINIO_ROOT_PASSWORD
docker compose up -d --build
```

First build takes a few minutes (image pulls + custom image builds). Subsequent starts are fast.

### Notes on running alongside other Docker projects

- `COMPOSE_PROJECT_NAME=wfm` namespaces every container, volume, and network under `wfm_*`, so this project never collides with unrelated Docker projects on the same machine.
- Host ports are intentionally non-default (`5433` for Postgres, `8081` for Airflow, `5001` for MLflow) to reduce the chance of port conflicts. If a port is still taken, just change the corresponding value in `.env`.

### Verify the stack

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8081 | as set in `.env` |
| MLflow | http://localhost:5001 | none |
| MinIO console | http://localhost:9001 | as set in `.env` |

MinIO should already contain two buckets (`mlflow-artifacts`, `wfm-datalake`), created automatically on first startup.

### Useful commands

```bash
docker compose stop          # stop containers, keep data
docker compose down          # remove containers, keep volumes
docker compose down -v       # remove containers and volumes (full reset)
docker compose logs -f <service>
```

## Modules

### Data simulation
Generates synthetic call/ticket events (non-homogeneous Poisson process for realistic intraday/weekly/seasonal patterns) and an agent registry (skills, tenure, absence history), since real production data isn't available.

### Forecasting
Predicts demand volume at 15-min / hourly / daily horizons. Compares Prophet, SARIMA, and a deep learning baseline (LSTM / TFT).

### Scheduling optimization
Converts a demand forecast into required staffing (Erlang C) and generates a cost-minimizing schedule under constraints (max hours, mandatory rest days, required skills) using linear programming (OR-Tools).

### Attrition risk
Predicts agent departure risk (XGBoost / survival analysis) with SHAP-based explainability per agent.

### What-if simulator
Lets a user adjust volume, headcount, and absenteeism assumptions and see the resulting SLA/cost impact instantly.

## Model training, validation & testing

**Forecasting** — time-based split (70/15/15, chronological, never shuffled), walk-forward (rolling origin) cross-validation, evaluated against MAE / RMSE / MAPE and a naive baseline (same slot, previous week). The selected model must beat the naive baseline consistently across multiple validation windows, not just on average.

**Attrition** — stratified 70/15/15 split (target is imbalanced), stratified k-fold (k=5) for hyperparameter tuning, evaluated on AUC-ROC, precision/recall, F1 — recall is prioritized, since missing a departure is costlier than a false alarm. SHAP values used for per-agent and global explainability.

**Scheduling optimization** — not supervised ML, so validated by simulation: the proposed schedule is replayed against historical demand to measure the SLA it would have achieved, rather than through a train/test split.

All experiments (forecasting and attrition) are tracked in MLflow: parameters, metrics, and artifacts for every run, with a model registry distinguishing staging vs production versions.

## Testing strategy

- Unit tests (pytest): feature engineering functions, API endpoints, optimization solver logic
- Integration tests: Airflow DAGs run against a small sample dataset
- Model regression guard: a candidate model only replaces the production model if it improves validation metrics by a defined margin

## Roadmap

- [x] Infrastructure setup (Postgres, MinIO, Airflow, MLflow, Docker Compose)
- [x] Data simulator + ingestion DAG
- [X] Forecasting models (Prophet, SARIMA, walk-forward validation)
- [X] Attrition model (XGBoost, SHAP)
- [X] Scheduling optimization (Erlang C, OR-Tools)
- [X] FastAPI backend
- [ ] Dashboard
- [ ] What-if simulator
- [ ] Drift monitoring (Evidently AI)
- [ ] Tests + documentation + demo

### Possible extensions

- Reinforcement learning for dynamic schedule optimization
- Real-time alerting via websockets
- Multi-user auth (supervisor vs admin)
- Cloud deployment