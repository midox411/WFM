"""
Central configuration for the synthetic data simulator.
Change values here to scale the dataset up/down without touching generation logic.
"""
from datetime import date

# --- Scale ---
NUM_AGENTS = 100
START_DATE = date(2025, 8, 1)
END_DATE = date(2026, 7, 31)          # 12 months of history
TARGET_DAILY_CALLS = 10_000            # approximate average, actual varies with seasonality

# --- Skills / queues ---
SKILLS = [
    {"skill_id": 1, "skill_name": "Customer Service", "weight": 0.45},
    {"skill_id": 2, "skill_name": "Technical Support", "weight": 0.25},
    {"skill_id": 3, "skill_name": "Billing", "weight": 0.20},
    {"skill_id": 4, "skill_name": "Retention", "weight": 0.10},
]

# --- Agents ---
ATTRITION_RATE = 0.18          # ~18% of the 100 agents will have a termination_date
TEAMS = ["Team A", "Team B", "Team C"]
SITE = "Casablanca"

# --- Shifts & breaks ---
# Full-time shift patterns: (start_hour, end_hour) — 9h span = 8h worked + 1h lunch.
# Staggering start times across agents avoids everyone hitting peak hours identically.
FULL_TIME_SHIFT_PATTERNS = [(8, 17), (9, 18)]
PART_TIME_SHIFT_HOURS = 5   # single shift, no lunch, one short break

SHORT_BREAK_MIN = 15
LUNCH_BREAK_MIN = 60
OPEN_HOUR = 8
CLOSE_HOUR = 20   # exclusive, so last calls arrive in the 19:00-19:59 slot

# Relative weight per hour of day (index = hour), only OPEN_HOUR..CLOSE_HOUR-1 matter.
# Single dominant morning peak (9h-11h), steady decline through the afternoon.
HOURLY_WEIGHTS = {
    8: 0.5, 9: 1.1, 10: 1.5, 11: 1.4, 12: 0.7,
    13: 0.6, 14: 0.9, 15: 0.8, 16: 0.7, 17: 0.6,
    18: 0.5, 19: 0.4,
}

# Relative weight per day of week (0=Monday .. 6=Sunday).
# Monday/Tuesday are the busiest (backlog from the weekend), Friday tapers off,
# weekend is light (skeleton operation).
DOW_WEIGHTS = {0: 1.3, 1: 1.15, 2: 1.0, 3: 0.95, 4: 0.85, 5: 0.5, 6: 0.35}

# Relative weight per month (1-12) - mimics seasonality (higher Nov/Dec, lower Aug = summer break)
MONTH_WEIGHTS = {
    1: 1.05, 2: 1.0, 3: 1.0, 4: 0.95, 5: 0.95, 6: 1.0,
    7: 1.05, 8: 0.75, 9: 1.0, 10: 1.1, 11: 1.25, 12: 1.3,
}

# --- Realism controls (avoid an overly clean/deterministic signal for ML) ---
DAILY_NOISE_STD = 0.16          # base white noise on daily volume (was 0.06 - too clean)
NOISE_AUTOCORR = 0.6            # AR(1) coefficient: today's noise correlates with yesterday's
TREND_GROWTH = 0.18             # overall volume grows ~18% from start to end of the window
HOURLY_JITTER = 0.12            # daily jitter applied to the intraday curve shape

ANOMALY_PROB = 0.02             # ~2% of days get an unexplained spike or drop
ANOMALY_SPIKE_RANGE = (1.4, 2.0)   # e.g. marketing push, external outage elsewhere
ANOMALY_DIP_RANGE = (0.25, 0.55)   # e.g. system outage, office closure
# Islamic-calendar holiday dates are approximate (lunar calendar shifts each year) -
# fine for simulation purposes, not meant to be exact. Value = volume multiplier
# (skeleton operation: most people don't call, but a few emergencies still do).
HOLIDAYS = {
    date(2025, 8, 14): 0.15,   # Revolution Day
    date(2025, 8, 20): 0.15,   # Youth Day
    date(2025, 8, 21): 0.20,   # Oued Ed-Dahab Day
    date(2025, 9, 5):  0.15,   # Mawlid (approx.)
    date(2025, 11, 6): 0.15,   # Green March Day
    date(2025, 11, 18): 0.15,  # Independence Day
    date(2026, 1, 1):  0.10,   # New Year's Day
    date(2026, 1, 11): 0.20,   # Independence Manifesto Day
    date(2026, 1, 14): 0.20,   # Amazigh New Year
    date(2026, 3, 20): 0.10,   # Eid al-Fitr (approx.)
    date(2026, 3, 21): 0.20,   # Eid al-Fitr, day 2 (approx.)
    date(2026, 5, 1):  0.10,   # Labour Day
    date(2026, 5, 27): 0.10,   # Eid al-Adha (approx.)
    date(2026, 6, 17): 0.20,   # Islamic New Year (approx.)
    date(2026, 7, 30): 0.15,   # Throne Day
}

# --- Call outcome probabilities (base rates, adjusted for peak hours in generation code) ---
BASE_ABANDON_RATE = 0.07
BASE_TRANSFER_RATE = 0.04
PEAK_HOURS = {9, 10, 11}
PEAK_ABANDON_MULTIPLIER = 1.8   # abandonment rises when the queue is under pressure

RANDOM_SEED = 42