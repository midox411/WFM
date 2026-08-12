"""
Configuration for the scheduling optimization module (Day 13).
Erlang C parameters and OR-Tools scheduling constraints.
"""
import os

# --- Database (same pattern as attrition/build_features.py) ---
POSTGRES_CONN = "postgresql+psycopg2://{user}:{pwd}@postgres:5432/{db}"

# --- MLflow ---
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MLFLOW_EXPERIMENT = "wfm_optimization"

# --- Data paths (Spark-processed outputs) ---
PROCESSED_DIR = "/opt/wfm_data/processed"
VOLUME_15MIN_PATH = f"{PROCESSED_DIR}/volume_15min"   # Parquet: date, hour, slot_15, call_volume
OUTPUT_SCHEDULE_PATH = f"{PROCESSED_DIR}/optimized_schedule.csv"

# --- Erlang C parameters ---
# Target Service Level: % of calls answered within ANSWER_TIME_SEC seconds
SERVICE_LEVEL_TARGET = 0.80          # 80 %
ANSWER_TIME_SEC = 20                 # 20-second threshold (industry standard)
AVG_HANDLE_TIME_SEC = 240            # Average Handle Time: 4 minutes per call
SLOT_DURATION_MIN = 15               # 15-minute slots
OPEN_HOUR = 8                        # Centre opens at 08:00
CLOSE_HOUR = 20                      # Centre closes at 20:00 (exclusive)
SLOTS_PER_DAY = (CLOSE_HOUR - OPEN_HOUR) * (60 // SLOT_DURATION_MIN)  # 48 slots

# --- OR-Tools scheduling constraints ---
PLANNING_DAYS = 7                    # One week horizon
MAX_HOURS_FULL_TIME = 40             # hours/week for full-time agents
MAX_HOURS_PART_TIME = 20             # hours/week for part-time agents
MIN_REST_DAYS = 2                    # minimum days OFF per week

# --- Shift duration (fixed per contract type) ---
# Each agent who works a given day works exactly one contiguous block of this length.
# This prevents the solver from assigning isolated 15-min micro-slots.
SHIFT_DUR_FULL_TIME_SLOTS = 32       # full-time  : 8h  = 32 × 15min slots
SHIFT_DUR_PART_TIME_SLOTS = 16       # part-time  : 4h  = 16 × 15min slots

SKILL_ID_DEFAULT = 1                 # fallback skill if agent_skills unavailable

# Safety cap: never require more than this many agents on a single slot
# (avoids Erlang C blowing up on artificially high simulated peaks)
MAX_AGENTS_PER_SLOT = 30