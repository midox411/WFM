# WFM Intelligence Platform

Plateforme de gestion prévisionnelle des effectifs (Workforce Management) combinant forecasting, optimisation de planning et prédiction du risque d'attrition, avec une couche MLOps complète et un dashboard interactif.

Projet de fin d'études — Master Big Data & Cloud Computing.

---

## 1. Contexte et objectif

Dans un centre d'appels/opérations, trois problèmes sont historiquement traités séparément :
1. **Prévoir** la charge de travail (volume d'appels/tickets à venir)
2. **Planifier** les effectifs en conséquence (qui travaille quand)
3. **Anticiper** le risque de départ des agents (turnover, burnout)

Ce projet unifie ces trois problèmes dans une seule plateforme data-driven, avec un simulateur de scénarios ("what-if") permettant de tester l'impact de décisions RH avant de les appliquer.

**Pourquoi ce sujet** : il s'appuie sur une expérience professionnelle réelle (analyste workforce chez Foundever/FedEx) et couvre l'ensemble du spectre data science — de l'ingénierie de données à grande échelle jusqu'au MLOps, en passant par le ML supervisé, les séries temporelles et l'optimisation combinatoire.

---

## 2. Architecture générale

```
                     ┌─────────────────────────────────────────┐
                     │              DATA SOURCES                │
                     │   Simulateur d'événements (Faker/Poisson) │
                     └───────────────────┬───────────────────────┘
                                          │
                              ┌───────────▼───────────┐
                              │   Apache Airflow (DAGs) │
                              │   orchestration ETL     │
                              └───────────┬───────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
             ┌──────▼──────┐      ┌───────▼───────┐     ┌───────▼───────┐
             │ Apache Spark │      │  PostgreSQL   │     │  MinIO (S3)   │
             │ (agrégation) │      │ (données prod)│     │ (données brutes)│
             └──────┬──────┘      └───────┬───────┘     └───────────────┘
                    │                     │
        ┌───────────┴─────────────────────┴───────────┐
        │              COUCHE MODÈLES ML                │
        │  Forecasting │ Optimisation │ Attrition risk  │
        │  (MLflow tracking + registry)                 │
        └───────────────────┬───────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  FastAPI (API)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Dashboard (React│
                    │ ou Streamlit)   │
                    └─────────────────┘

        Monitoring transverse : Evidently AI (drift) + MLflow (expériences)
        Conteneurisation transverse : Docker Compose (tous les services)
```

---

## 3. Structure du dépôt

```
wfm-platform/
├── docker-compose.yml
├── .env.example
├── README.md
├── data/
│   ├── simulator/              # génération de données synthétiques
│   └── raw/, processed/        # montés en volumes (MinIO en local)
├── airflow/
│   ├── dags/
│   │   ├── dag_ingestion.py
│   │   ├── dag_spark_aggregation.py
│   │   └── dag_model_retrain.py
│   └── plugins/
├── spark_jobs/
│   └── aggregate_call_volumes.py
├── ml/
│   ├── forecasting/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── models/ (prophet.py, sarima.py, tft.py)
│   ├── attrition/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   └── explain.py (SHAP)
│   ├── optimization/
│   │   └── scheduler_solver.py (OR-Tools)
│   └── common/
│       ├── data_validation.py
│       └── mlflow_utils.py
├── api/
│   ├── main.py (FastAPI)
│   ├── routers/
│   │   ├── forecast.py
│   │   ├── schedule.py
│   │   ├── attrition.py
│   │   └── whatif.py
│   └── schemas/
├── monitoring/
│   └── evidently_reports.py
├── frontend/
│   └── (React + Recharts, ou app Streamlit)
└── tests/
    ├── test_data_pipeline.py
    ├── test_forecasting.py
    ├── test_optimization.py
    └── test_api.py
```

---

## 4. Détail par section — quoi, pourquoi, comment

### 4.1 Génération de données (simulateur)

**Quoi** : comme les vraies données FedEx/Foundever sont confidentielles, un simulateur génère un jeu de données réaliste à grande échelle (des millions d'événements).

**Pourquoi** : démontrer la capacité à construire un pipeline Big Data même sans dataset Kaggle prêt à l'emploi, et contrôler des scénarios de test (pics, saisonnalité, absentéisme).

**Comment** :
- Processus de Poisson non-homogène pour générer les arrivées d'appels (intensité variable selon l'heure/jour/saison)
- Génération d'un référentiel agents (compétences, ancienneté, historique d'absences, historique de départ) via Faker
- Injection volontaire de patterns réalistes : pics du lundi matin, creux du vendredi après-midi, saisonnalité mensuelle
- Sortie : fichiers CSV/Parquet déposés dans MinIO, simulant un export type Five9

### 4.2 Ingestion et orchestration (Airflow)

**Quoi** : 3 DAGs principaux — ingestion quotidienne, agrégation Spark, réentraînement des modèles.

**Pourquoi** : montrer une orchestration réaliste type production, pas juste un notebook exécuté à la main.

**Comment** :
- `dag_ingestion` : dépose les nouveaux fichiers simulés dans MinIO, valide le schéma (Great Expectations ou pandera), charge dans PostgreSQL
- `dag_spark_aggregation` : agrège les événements bruts en séries temporelles (volume par 15 min, par file/skill)
- `dag_model_retrain` : déclenché de façon hebdomadaire, réentraîne le modèle de forecasting si drift détecté

### 4.3 Traitement Big Data (Spark)

**Quoi** : agrégation des événements bruts (potentiellement des millions de lignes) en tables prêtes pour le ML.

**Comment** : jobs PySpark lisant depuis MinIO, agrégations groupBy (date, heure, file), écriture en Parquet partitionné dans PostgreSQL/MinIO.

### 4.4 Forecasting (prévision de la demande)

**Quoi** : prédire le volume d'appels/tickets à 15 min, 1h et 1 jour d'horizon.

**Modèles comparés** :
- Prophet (baseline, gère bien saisonnalité/jours fériés)
- SARIMA (statsmodels, baseline statistique classique)
- Temporal Fusion Transformer ou LSTM (PyTorch, capture les dépendances complexes)

**Entraînement / validation / test** :
- Split **temporel** (jamais aléatoire pour des séries temporelles) : 70% train / 15% validation / 15% test, dans l'ordre chronologique
- Validation croisée **walk-forward** (rolling origin) : réentraînement progressif sur fenêtres glissantes pour simuler des conditions réelles de production
- Métriques : MAE, RMSE, MAPE, et comparaison contre une baseline naïve (valeur du même créneau la semaine précédente)
- Le modèle retenu est celui qui bat la baseline naïve avec la marge la plus stable sur plusieurs fenêtres de validation, pas seulement la meilleure moyenne
- Tracking de toutes les expériences (hyperparamètres, métriques, artefacts) dans **MLflow**

### 4.5 Optimisation des plannings

**Quoi** : générer un planning d'agents qui respecte le SLA cible au moindre coût.

**Comment** :
- Modèle d'Erlang C pour estimer le nombre d'agents nécessaires par créneau à partir de la prévision de volume
- Programmation linéaire en nombres entiers (OR-Tools ou PuLP) pour affecter les agents aux créneaux sous contraintes : heures max/agent, jours de repos obligatoires, compétences requises, coût
- Sortie : planning optimisé + comparatif coût/couverture SLA vs planning manuel

**Validation** : pas de "test set" classique ici (c'est de l'optimisation, pas du ML supervisé) — validation par simulation : on rejoue le planning proposé sur les données historiques réelles et on mesure le SLA simulé obtenu.

### 4.6 Prédiction du risque d'attrition

**Quoi** : score de probabilité de départ par agent, avec explication des facteurs.

**Modèles** :
- XGBoost / Random Forest pour la classification binaire (départ dans les 3 prochains mois)
- Modèle de survie (lifelines, Cox Proportional Hazards) en complément, pour estimer un "temps avant départ" plutôt qu'une simple probabilité

**Entraînement / validation / test** :
- Split stratifié 70/15/15 (stratifié sur la variable cible car déséquilibrée — peu d'agents partent réellement)
- Validation croisée en k-fold stratifié (k=5) sur le train, pour le tuning d'hyperparamètres (GridSearch/Optuna)
- Métriques : AUC-ROC, précision/rappel, F1 (le rappel est priorisé — rater un départ coûte plus cher qu'une fausse alerte)
- Explicabilité via **SHAP** (valeurs SHAP par agent et importance globale des features)

### 4.7 Simulateur what-if

**Quoi** : interface à sliders pour tester l'impact de scénarios (volume +20%, -2 agents, absentéisme +5%) sur le SLA et le coût, sans toucher aux données réelles.

**Comment** : ré-exécution à la volée du calcul Erlang C + solveur d'optimisation sur les paramètres modifiés, affichage instantané des nouveaux indicateurs.

### 4.8 API (FastAPI)

Expose chaque module via des endpoints REST : `/forecast`, `/schedule/optimize`, `/attrition/score`, `/whatif/simulate`. Validation des entrées/sorties via Pydantic. Documentation automatique via Swagger (`/docs`).

### 4.9 Dashboard

Consomme l'API. Deux options possibles :
- **Streamlit** : plus rapide à développer, suffisant pour une démo convaincante
- **React + Recharts/Plotly** : rendu plus "produit", recommandé si le temps le permet (semaine 3)

### 4.10 MLOps et monitoring

- **MLflow** : tracking des expériences (tous les modèles), model registry (versions "staging"/"production")
- **Evidently AI** : rapports de data drift et de model drift, comparant la distribution des données de production simulées à celle du train
- Déclenchement automatique de réentraînement si le drift dépasse un seuil (relié au DAG Airflow)

---

## 5. Stack technique et conteneurisation

Tout le projet est conteneurisé via **Docker Compose**, pour une exécution reproductible en une seule commande.

| Service | Rôle | Image de base |
|---|---|---|
| `postgres` | Base de données applicative | postgres:16 |
| `minio` | Stockage objet (data lake) | minio/minio |
| `airflow-webserver` / `airflow-scheduler` | Orchestration | apache/airflow:2.9 |
| `spark-master` / `spark-worker` | Traitement distribué | bitnami/spark |
| `mlflow` | Tracking et registry ML | ghcr.io/mlflow/mlflow |
| `api` | Backend FastAPI | python:3.11-slim (Dockerfile custom) |
| `frontend` | Dashboard | node:20-alpine (build) servi via nginx, ou streamlit custom |
| `redis` | Cache API / broker Airflow | redis:7 |

**Pourquoi tout dockeriser** : c'est un argument fort en entretien ("le projet se lance avec `docker compose up`") et ça évite les problèmes de compatibilité entre Spark/Airflow/Python qui sont notoirement pénibles à installer nativement.

**Commande de lancement cible** :
```bash
docker compose up -d
# Airflow UI     : localhost:8080
# MLflow UI      : localhost:5000
# MinIO console  : localhost:9001
# API docs       : localhost:8000/docs
# Dashboard      : localhost:8501 (Streamlit) ou 3000 (React)
```

---

## 6. Stratégie de tests

- **Tests unitaires** (pytest) : fonctions de feature engineering, endpoints API, fonctions du solveur d'optimisation
- **Tests d'intégration** : DAG Airflow exécuté en mode test sur un petit échantillon de données
- **Tests de non-régression modèle** : un modèle candidat ne remplace le modèle en production que s'il améliore les métriques de validation d'au moins X% (seuil à définir, ex. 2%)

---

## 7. Planning sur 3 semaines

Hypothèse : usage intensif de l'IA (Claude Code/assistants) pour accélérer l'implémentation — le planning est donc orienté **décisions et validations**, pas frappe de code ligne à ligne.

### Semaine 1 — Fondations et données
- Jour 1-2 : setup repo, Docker Compose (Postgres, MinIO, Airflow, MLflow), structure du projet
- Jour 3-4 : simulateur de données (Poisson non-homogène + Faker), génération du jeu de données complet, chargement dans MinIO/Postgres
- Jour 5-6 : premier DAG Airflow (ingestion), job Spark d'agrégation basique
- Jour 7 : buffer / debug infra (c'est souvent là que ça bloque)

**Livrable fin S1** : pipeline de données fonctionnel de bout en bout, données prêtes pour le ML.

### Semaine 2 — Modèles ML
- Jour 8-9 : forecasting — baseline Prophet + SARIMA, split temporel, walk-forward validation, tracking MLflow
- Jour 10 : forecasting avancé (LSTM/TFT) si le temps le permet, sinon rester sur Prophet/SARIMA et documenter le choix
- Jour 11-12 : modèle d'attrition (XGBoost), split stratifié + k-fold, métriques, SHAP
- Jour 13 : module d'optimisation (Erlang C + OR-Tools)
- Jour 14 : intégration des 3 modèles dans l'API FastAPI

**Livrable fin S2** : API fonctionnelle exposant forecasting, attrition, optimisation, avec modèles trackés dans MLflow.

### Semaine 3 — Dashboard, MLOps, finitions
- Jour 15-16 : dashboard (Streamlit en priorité, migration React si le temps le permet), connexion à l'API
- Jour 17 : simulateur what-if
- Jour 18 : monitoring de drift (Evidently AI) + DAG de réentraînement automatique
- Jour 19 : tests (unitaires + intégration), nettoyage du code, gestion des erreurs
- Jour 20-21 : documentation finale, préparation de la démo/soutenance, README, captures d'écran, éventuellement une vidéo de démo

**Livrable fin S3** : projet complet, dockerisé, démontrable en une commande, documenté.

---

## 8. Pistes d'amélioration (si temps disponible / V2)

- Reinforcement Learning pour l'optimisation dynamique des plannings (au-delà de la programmation linéaire statique)
- API de notifications temps réel (alertes sous-effectif via websockets)
- Authentification multi-utilisateurs (superviseur vs admin) sur le dashboard
- Déploiement cloud (Oracle Cloud, en cohérence avec les compétences déjà mentionnées au CV)
