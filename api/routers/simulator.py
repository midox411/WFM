import math
import os
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

VOLUME_PATH = "/opt/wfm_data/processed/volume_15min"
BASELINE_WEEKLY_COST = 115931.0  # Real cost from Jour 13 OR-Tools optimal run

# ---------------------------------------------------------------------------
# Erlang C & SLA Pure Math Functions
# ---------------------------------------------------------------------------
def _erlang_c(n: int, a: float) -> float:
    if n <= 0 or a <= 0:
        return 0.0
    if a >= n:
        return 1.0
    poisson_sum = 0.0
    t = 1.0
    for k in range(n):
        poisson_sum += t
        t *= a / (k + 1)
    b_term = t * n / (n - a)
    ec = b_term / (poisson_sum + b_term)
    return float(max(0.0, min(1.0, ec)))


def service_level(n: int, a: float, answer_time_sec: float = 20.0, aht_sec: float = 240.0) -> float:
    if n <= 0:
        return 0.0
    if a >= n:
        return 0.0
    ec = _erlang_c(n, a)
    exponent = -(n - a) * answer_time_sec / aht_sec
    sl = 1.0 - ec * math.exp(exponent)
    return float(max(0.0, min(1.0, sl)))


def agents_required(
    call_volume: float,
    slot_min: int = 15,
    aht_sec: float = 240.0,
    target_sl: float = 0.80,
    answer_time_sec: float = 20.0,
    max_agents: int = 60,
) -> int:
    if call_volume <= 0:
        return 0
    slot_sec = slot_min * 60
    arrival_rate = call_volume / slot_sec
    a = arrival_rate * aht_sec
    n_min = max(1, math.ceil(a) + 1)
    for n in range(n_min, max_agents + 1):
        sl = service_level(n, a, answer_time_sec, aht_sec)
        if sl >= target_sl:
            return n
    return max_agents


# ---------------------------------------------------------------------------
# Request Model
# ---------------------------------------------------------------------------
class WhatIfRequest(BaseModel):
    volume_change_pct: float = 0.0        # e.g., +10.0 or -15.0
    headcount_delta: int = 0              # e.g., +5 or -10 agents
    absenteeism_rate_pct: float = 5.0     # e.g., 5.0% absenteeism rate


# ---------------------------------------------------------------------------
# Core Simulation Helper
# ---------------------------------------------------------------------------
def run_simulation(volume_change_pct: float, headcount_delta: int, absenteeism_rate_pct: float):
    # 1. Load baseline intraday 15min volume pattern
    try:
        if os.path.exists(VOLUME_PATH):
            df = pd.read_parquet(VOLUME_PATH)
            df = df.fillna(0)
            if "slot_15" in df.columns:
                grouped = df.groupby("slot_15")["call_volume"].mean() if "call_volume" in df.columns else df.groupby("slot_15")["volume"].mean()
                base_volumes = [float(grouped.get(i, 20.0)) for i in range(48)]
            else:
                base_volumes = [float(df["call_volume"].iloc[i % len(df)]) for i in range(48)]
        else:
            # Fallback realistic bell-curve pattern if parquet not found
            base_volumes = [
                float(max(5, int(35 * math.sin(math.pi * i / 48) ** 2))) for i in range(48)
            ]
    except Exception:
        base_volumes = [
            float(max(5, int(35 * math.sin(math.pi * i / 48) ** 2))) for i in range(48)
        ]

    # 2. Compute baseline and simulated metrics per 15-min slot
    vol_factor = 1.0 + (volume_change_pct / 100.0)
    base_headcount = 82  # total active workforce in DB
    effective_headcount = max(10, base_headcount + headcount_delta)
    absence_factor = 1.0 - (max(0.0, min(50.0, absenteeism_rate_pct)) / 100.0)
    
    # Average agents present per slot during operational window (8h shift / 12h open window)
    present_agents_avg = effective_headcount * absence_factor * (5.0 / 7.0) * (8.0 / 12.0)

    intraday_data = []
    base_req_list = []
    sim_req_list = []
    sla_sim_list = []
    covered_slots = 0

    for i in range(48):
        v_base = base_volumes[i]
        v_sim = max(0.0, v_base * vol_factor)

        n_req_base = agents_required(v_base)
        n_req_sim = agents_required(v_sim)

        base_req_list.append(n_req_base)
        sim_req_list.append(n_req_sim)

        # Scale available agents based on intraday demand profile shape
        max_sim = max(1, max(sim_req_list or [1]))
        shape_factor = (n_req_sim / max_sim) if max_sim > 0 else 1.0
        n_avail_slot = max(1, round(present_agents_avg * (0.6 + 0.8 * shape_factor)))

        # Service level for simulated slot
        arrival_rate = v_sim / (15 * 60)
        a_load = arrival_rate * 240.0
        sl_sim = service_level(n_avail_slot, a_load, 20.0, 240.0)
        sla_sim_list.append(sl_sim)

        if n_avail_slot >= n_req_sim:
            covered_slots += 1

        h = 8 + (i * 15) // 60
        m = (i * 15) % 60
        time_str = f"{h:02d}:{m:02d}"

        intraday_data.append({
            "slot": i,
            "time": time_str,
            "volume_base": round(v_base, 1),
            "volume_sim": round(v_sim, 1),
            "agents_req_base": n_req_base,
            "agents_req_sim": n_req_sim,
            "agents_available": n_avail_slot,
            "service_level_pct": round(sl_sim * 100.0, 1)
        })

    # 3. Aggregated Summary
    avg_sla = float(sum(sla_sim_list) / len(sla_sim_list)) * 100.0
    coverage_rate = float(covered_slots / 48.0) * 100.0
    peak_req_base = max(base_req_list)
    peak_req_sim = max(sim_req_list)

    # Cost simulation logic:
    simulated_cost = BASELINE_WEEKLY_COST * vol_factor * (1.0 + (absenteeism_rate_pct - 5.0) / 100.0)
    cost_delta = simulated_cost - BASELINE_WEEKLY_COST
    cost_delta_pct = (cost_delta / BASELINE_WEEKLY_COST) * 100.0

    return {
        "summary": {
            "volume_change_pct": volume_change_pct,
            "headcount_delta": headcount_delta,
            "absenteeism_rate_pct": absenteeism_rate_pct,
            "peak_agents_req_base": peak_req_base,
            "peak_agents_req_sim": peak_req_sim,
            "avg_service_level_pct": round(avg_sla, 1),
            "coverage_rate_pct": round(coverage_rate, 1),
            "baseline_weekly_cost": round(BASELINE_WEEKLY_COST, 2),
            "simulated_weekly_cost": round(simulated_cost, 2),
            "cost_delta": round(cost_delta, 2),
            "cost_delta_pct": round(cost_delta_pct, 1),
            "effective_workforce": effective_headcount,
        },
        "intraday": intraday_data
    }


# ---------------------------------------------------------------------------
# Endpoints (Supports both GET and POST)
# ---------------------------------------------------------------------------
@router.get("/what-if")
def get_what_if_simulation(
    volume_change_pct: float = Query(0.0, description="Variation du volume d'appels (%)"),
    headcount_delta: int = Query(0, description="Variation de l'effectif d'agents (+/-)"),
    absenteeism_rate_pct: float = Query(5.0, description="Taux d'absentéisme (%)")
):
    """Exécute une simulation What-if interactive basée sur Erlang C et le profil intraday"""
    try:
        return run_simulation(volume_change_pct, headcount_delta, absenteeism_rate_pct)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de simulation What-if: {str(e)}")


@router.post("/what-if")
def post_what_if_simulation(req: WhatIfRequest):
    """Exécute une simulation What-if interactive via corps JSON"""
    try:
        return run_simulation(req.volume_change_pct, req.headcount_delta, req.absenteeism_rate_pct)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de simulation What-if: {str(e)}")
