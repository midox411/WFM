"""
OR-Tools CP-SAT scheduler — fixed-shift contiguous model.

Formulation (Day 13 — v3):
  Instead of independent work[a,d,s] booleans per 15-min slot (which allows the
  solver to assign isolated micro-slots), we use shift_start[a,d,v] variables:

    start[a,d,v] = 1  iff  agent a begins their shift at slot v on day d

  Shift duration is FIXED per contract type:
    - full_time : SHIFT_DUR_FT slots  (e.g. 32 = 8h)
    - part_time : SHIFT_DUR_PT slots  (e.g. 16 = 4h)

  Contiguity is guaranteed BY CONSTRUCTION: if start[a,d,v]=1, the agent covers
  slots v, v+1, ..., v+shift_dur-1 continuously. No separate contiguity
  constraints are needed, and no auxiliary "rising edge" variables are required.

  Model size (82 agents, 7 days):
    - start vars : 82 × 7 × ~17–33 ≈ 10–19 K BoolVars
    - works_day  : 82 × 7 = 574    BoolVars
    - Total      : ~10–20 K  (vs ~55K with the previous rising-edge approach)

Constraints (in order):
  1. Coverage   : every (day, slot) has >= Erlang C staffing requirement
  2. At most 1  : each agent has at most one shift per day
  3. Max days   : total working days per week <= floor(max_hours / shift_duration)
  4. Rest days  : working days <= PLANNING_DAYS - MIN_REST_DAYS

Objective: minimise total wage cost = sum of (shift_duration × hourly_rate) per working day.
"""
import pandas as pd

try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("WARNING: ortools not available — scheduler will return a greedy fallback schedule.")

import config


# ---------------------------------------------------------------------------
# Shift duration per contract type (fixed per working day)
# ---------------------------------------------------------------------------
SHIFT_DUR_FT = getattr(config, "SHIFT_DUR_FULL_TIME_SLOTS", 32)   # 8h = 32 × 15min
SHIFT_DUR_PT = getattr(config, "SHIFT_DUR_PART_TIME_SLOTS", 16)   # 4h = 16 × 15min


def _shift_dur(contract_type: str) -> int:
    return SHIFT_DUR_FT if contract_type == "full_time" else SHIFT_DUR_PT


def _greedy_schedule(agents_df, staffing_req):
    """Simple greedy fallback when OR-Tools is not installed."""
    n_days  = len(staffing_req)
    n_slots = len(staffing_req[0]) if n_days > 0 else 0
    agent_ids = agents_df["agent_id"].tolist()
    n_agents  = len(agent_ids)
    rows = []
    for d in range(n_days):
        for s in range(n_slots):
            req = staffing_req[d][s]
            for i in range(min(req, n_agents)):
                rows.append({"agent_id": agent_ids[i % n_agents],
                             "day": d, "slot": s, "assigned": 1})
    return pd.DataFrame(rows)


def solve(
    agents_df: pd.DataFrame,
    agent_skills_df: pd.DataFrame,
    staffing_req: list,
    time_limit_sec: int = 120,
) -> dict:
    """
    Build and solve the CP-SAT shift-scheduling model.

    Parameters
    ----------
    agents_df       : active agents with contract_type, base_hourly_cost
    agent_skills_df : (unused in this version — kept for API compatibility)
    staffing_req    : list[list[int]] — shape [PLANNING_DAYS][SLOTS_PER_DAY]
    time_limit_sec  : solver time limit (default 120s; larger model than v2)

    Returns
    -------
    dict with keys: schedule_df, total_cost, coverage_rate,
                    solver_status, objective_value, best_bound
    """
    if not ORTOOLS_AVAILABLE:
        sched_df = _greedy_schedule(agents_df, staffing_req)
        return {
            "schedule_df":     sched_df,
            "total_cost":      0.0,
            "coverage_rate":   0.0,
            "solver_status":   "GREEDY_FALLBACK",
            "objective_value": 0.0,
            "best_bound":      0.0,
        }

    n_days          = config.PLANNING_DAYS
    n_slots         = config.SLOTS_PER_DAY
    slot_duration_h = config.SLOT_DURATION_MIN / 60.0

    agents         = agents_df.reset_index(drop=True)
    agent_ids      = agents["agent_id"].tolist()
    n_agents       = len(agent_ids)

    # Per-agent constants
    dur_a = [
        _shift_dur(agents.loc[a, "contract_type"])
        for a in range(n_agents)
    ]
    # Hourly cost as integer cents (OR-Tools needs integers)
    cost_cents_a = [
        int(round(agents.loc[a, "base_hourly_cost"] * 100))
        for a in range(n_agents)
    ]
    # Maximum working days per week (from weekly hour cap)
    max_days_a = [
        int(
            (config.MAX_HOURS_FULL_TIME if agents.loc[a, "contract_type"] == "full_time"
             else config.MAX_HOURS_PART_TIME)
            / (dur_a[a] * slot_duration_h)
        )
        for a in range(n_agents)
    ]

    # -----------------------------------------------------------------------
    # Build model
    # -----------------------------------------------------------------------
    model = cp_model.CpModel()

    # start[a, d, v] = 1 iff agent a starts their shift at slot v on day d
    start = {}
    for a in range(n_agents):
        dur = dur_a[a]
        n_valid_starts = n_slots - dur + 1          # valid start positions
        for d in range(n_days):
            for v in range(n_valid_starts):
                start[(a, d, v)] = model.NewBoolVar(f"s_a{a}_d{d}_v{v}")

    # works_day[a, d] = 1 iff agent a works on day d
    works_day = {}
    for a in range(n_agents):
        dur = dur_a[a]
        n_valid_starts = n_slots - dur + 1
        for d in range(n_days):
            wd = model.NewBoolVar(f"wd_a{a}_d{d}")
            works_day[(a, d)] = wd
            day_starts = [start[(a, d, v)] for v in range(n_valid_starts)]
            # At most one shift start per day
            model.Add(sum(day_starts) <= 1)
            # works_day is 1 iff exactly one start chosen
            model.Add(sum(day_starts) == wd)

    # -------------------------------------------------------------------
    # Constraint 1: Coverage — for each (day, slot) need >= req agents
    #
    # start[a,d,v] = 1 covers slot s  iff  v <= s < v + dur_a[a]
    #                                  iff  s - dur + 1 <= v <= s
    # -------------------------------------------------------------------
    for d in range(n_days):
        for s in range(n_slots):
            req = min(staffing_req[d][s], n_agents)
            if req == 0:
                continue
            coverage = []
            for a in range(n_agents):
                dur = dur_a[a]
                v_lo = max(0, s - dur + 1)
                v_hi = min(s, n_slots - dur)
                for v in range(v_lo, v_hi + 1):
                    coverage.append(start[(a, d, v)])
            if coverage:
                model.Add(sum(coverage) >= req)

    # -------------------------------------------------------------------
    # Constraint 2: Max working days per week
    # (equivalent to max weekly hours since shift duration is fixed)
    # -------------------------------------------------------------------
    for a in range(n_agents):
        model.Add(
            sum(works_day[(a, d)] for d in range(n_days)) <= max_days_a[a]
        )

    # -------------------------------------------------------------------
    # Constraint 3: Minimum rest days
    # -------------------------------------------------------------------
    for a in range(n_agents):
        model.Add(
            sum(works_day[(a, d)] for d in range(n_days))
            <= n_days - config.MIN_REST_DAYS
        )

    # -------------------------------------------------------------------
    # Objective: minimise total wage cost
    # cost per working day = shift_dur × slot_duration_h × hourly_rate
    # -------------------------------------------------------------------
    obj_terms = []
    for a in range(n_agents):
        # cost for one full working day for agent a (integer, in cents × 25)
        day_cost = cost_cents_a[a] * dur_a[a]
        for d in range(n_days):
            obj_terms.append(works_day[(a, d)] * day_cost)

    model.Minimize(sum(obj_terms))

    # -----------------------------------------------------------------------
    # Solve
    # -----------------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    solver.parameters.num_search_workers  = 4
    status = solver.Solve(model)

    status_map = {
        cp_model.OPTIMAL:       "OPTIMAL",
        cp_model.FEASIBLE:      "FEASIBLE",
        cp_model.INFEASIBLE:    "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN:       "UNKNOWN",
    }
    solver_status = status_map.get(status, "UNKNOWN")

    objective_val  = solver.ObjectiveValue()      if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0.0
    best_bound_val = solver.BestObjectiveBound()  if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0.0

    if solver_status == "OPTIMAL":
        print(f"OR-Tools: OPTIMAL (proven best) | Objective: {objective_val:.0f}")
    elif solver_status == "FEASIBLE":
        gap = (objective_val - best_bound_val) / objective_val if objective_val > 0 else 0.0
        print(f"OR-Tools: FEASIBLE (gap≈{gap*100:.1f}%, best in {time_limit_sec}s) "
              f"| Objective: {objective_val:.0f} | Bound: {best_bound_val:.0f}")
    else:
        print(f"OR-Tools: {solver_status}")

    # -----------------------------------------------------------------------
    # Extract schedule
    # -----------------------------------------------------------------------
    rows = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for a in range(n_agents):
            aid = agent_ids[a]
            dur = dur_a[a]
            n_valid_starts = n_slots - dur + 1
            for d in range(n_days):
                for v in range(n_valid_starts):
                    if solver.Value(start[(a, d, v)]) == 1:
                        for s in range(v, v + dur):
                            rows.append({"agent_id": aid, "day": d,
                                         "slot": s, "assigned": 1})
                        break   # only one start per day by construction

    schedule_df = (pd.DataFrame(rows) if rows
                   else pd.DataFrame(columns=["agent_id", "day", "slot", "assigned"]))

    # -----------------------------------------------------------------------
    # Cost and coverage
    # -----------------------------------------------------------------------
    total_cost = 0.0
    if not schedule_df.empty:
        merged = schedule_df.merge(
            agents_df[["agent_id", "base_hourly_cost"]], on="agent_id", how="left"
        )
        total_cost = float((merged["base_hourly_cost"] * slot_duration_h).sum())

    covered     = 0
    total_pairs = 0
    if not schedule_df.empty:
        counts = (schedule_df.groupby(["day", "slot"])["assigned"]
                  .sum().reset_index()
                  .rename(columns={"assigned": "n_assigned"}))
        for d in range(n_days):
            for s in range(n_slots):
                req = staffing_req[d][s]
                total_pairs += 1
                if req == 0:
                    covered += 1
                    continue
                match = counts[(counts["day"] == d) & (counts["slot"] == s)]
                n_assigned = int(match["n_assigned"].iloc[0]) if len(match) else 0
                if n_assigned >= req:
                    covered += 1

    coverage_rate = covered / total_pairs if total_pairs > 0 else 0.0

    return {
        "schedule_df":     schedule_df,
        "total_cost":      total_cost,
        "coverage_rate":   coverage_rate,
        "solver_status":   solver_status,
        "objective_value": objective_val,
        "best_bound":      best_bound_val,
    }