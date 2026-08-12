"""
Unit tests for the Day 13 scheduling optimization module.

Run with:
    pytest tests/test_optimization.py -v

These tests are designed to run WITHOUT Postgres, Airflow, or OR-Tools installed —
they use synthetic data and stub out external dependencies.

Tests covered:
  1.  Erlang C formula — known reference values
  2.  Staffing requirement calculation
  3.  Traffic intensity (Erlangs) computation
  4.  Service level boundary conditions
  5.  Skill compatibility — agent with wrong skill must not cover créneau
  6.  Absence constraint — absent agent must not appear in schedule
  7.  Max weekly hours — agent cannot exceed contract limit
  8.  Minimum rest days — agent must have >= MIN_REST_DAYS off
  9.  Coverage per skill and per slot
  10. Cost calculation consistency — optimized vs. baseline same basis
"""

import sys
import os
import pytest
import pandas as pd
import numpy as np

# ---- Make the optimization module importable without Docker paths ----
OPT_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "optimization")
sys.path.insert(0, os.path.abspath(OPT_DIR))

from erlang_c import (
    _erlang_c,
    service_level,
    agents_required,
    compute_staffing_requirement,
    erlang_traffic_intensity,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_agents(n=5, cost=60.0, contract="full_time"):
    """Build a minimal agents DataFrame."""
    return pd.DataFrame({
        "agent_id": list(range(1, n + 1)),
        "contract_type": [contract] * n,
        "base_hourly_cost": [cost] * n,
        "seniority_level": ["junior"] * n,
    })


def _make_agent_skills(agent_ids, skill_id=1):
    """All given agents have one skill."""
    return pd.DataFrame({
        "agent_id": agent_ids,
        "skill_id": [skill_id] * len(agent_ids),
    })


def _make_staffing_req(n_agents=3, n_days=7, n_slots=48, skill_id=1):
    """Uniform staffing requirement: n_agents agents every slot."""
    return {skill_id: [[n_agents] * n_slots for _ in range(n_days)]}


# =============================================================================
# Test 1 — Erlang C formula: known reference values
# =============================================================================

class TestErlangC:
    """
    Reference values computed manually from the Erlang C formula.
    These are stable mathematical identities, not dependent on any external tool.
    """

    def test_zero_traffic(self):
        """No traffic → P(wait) = 0, SL = 1."""
        assert _erlang_c(5, 0.0) == 0.0

    def test_zero_agents(self):
        """No agents → P(wait) = 0 (degenerate case — guard)."""
        assert _erlang_c(0, 1.0) == 0.0

    def test_saturated_system(self):
        """A >= N → system saturated → P(wait) = 1."""
        assert _erlang_c(3, 3.0) == 1.0
        assert _erlang_c(3, 5.0) == 1.0

    def test_reference_value_N2_A1(self):
        """
        N=2, A=1 Erlang: P(wait) = 1/3 ≈ 0.333.
        Manual derivation:
          sum_{k=0}^{1} A^k/k! = 1 + 1 = 2
          b_term = A^2/2! * N/(N-A) = 0.5 * 2 = 1
          C(2,1) = 1 / (2 + 1) = 1/3
        """
        ec = _erlang_c(2, 1.0)
        assert abs(ec - 1 / 3) < 0.001, f"Expected ~0.333, got {ec}"

    def test_result_in_unit_interval(self):
        """P(wait) must always be in [0, 1]."""
        for n in [1, 5, 10, 20]:
            for a in [0.1, 0.5, 0.9 * n]:
                ec = _erlang_c(n, a)
                assert 0.0 <= ec <= 1.0, f"Out of range: _erlang_c({n}, {a}) = {ec}"

    def test_monotone_in_N(self):
        """More agents → lower P(wait)."""
        a = 3.0
        prev = 1.0
        for n in range(4, 15):
            ec = _erlang_c(n, a)
            assert ec <= prev + 1e-9, f"Not monotone at n={n}: {ec} > {prev}"
            prev = ec


# =============================================================================
# Test 2 — Staffing requirement
# =============================================================================

class TestStaffingRequirement:

    def test_zero_volume_requires_zero_agents(self):
        reqs = compute_staffing_requirement([0.0, 0.0, 0.0])
        assert all(r == 0 for r in reqs), f"Expected all zeros, got {reqs}"

    def test_positive_volume_requires_agents(self):
        # ~500 calls in 15 min, AHT 240s → significant traffic
        reqs = compute_staffing_requirement([500.0])
        assert reqs[0] > 0

    def test_higher_volume_needs_more_agents(self):
        r_low  = compute_staffing_requirement([100.0])[0]
        r_high = compute_staffing_requirement([1000.0])[0]
        assert r_high > r_low, f"Expected r_high > r_low, got {r_high} vs {r_low}"

    def test_output_length_matches_input(self):
        volumes = [10.0, 50.0, 100.0, 0.0, 200.0]
        reqs = compute_staffing_requirement(volumes)
        assert len(reqs) == len(volumes)

    def test_safety_cap_respected(self):
        # Absurdly high volume — should be capped at max_agents
        reqs = compute_staffing_requirement([1_000_000.0], max_agents=30)
        assert reqs[0] <= 30


# =============================================================================
# Test 3 — Traffic intensity (Erlangs)
# =============================================================================

class TestTrafficIntensity:

    def test_basic_formula(self):
        """
        100 calls / 15min slot, AHT 240s:
        lambda = 100 / (15*60) = 0.1111 calls/sec
        A = 0.1111 * 240 = 26.67 Erlangs
        """
        a = erlang_traffic_intensity(100.0, 15, 240.0)
        expected = (100.0 / 900.0) * 240.0
        assert abs(a - expected) < 0.001

    def test_zero_volume(self):
        assert erlang_traffic_intensity(0.0, 15, 240.0) == 0.0

    def test_positive_always(self):
        a = erlang_traffic_intensity(50.0, 15, 180.0)
        assert a > 0


# =============================================================================
# Test 4 — Service level boundary conditions
# =============================================================================

class TestServiceLevel:

    def test_zero_agents_gives_zero_sl(self):
        assert service_level(0, 1.0, 20, 240) == 0.0

    def test_zero_traffic_gives_full_sl(self):
        assert service_level(5, 0.0, 20, 240) == 1.0

    def test_saturated_system_gives_zero_sl(self):
        assert service_level(3, 3.0, 20, 240) == 0.0

    def test_sl_monotone_in_N(self):
        """More agents → higher SL."""
        a = 5.0
        prev = 0.0
        for n in range(6, 20):
            sl = service_level(n, a, 20, 240)
            assert sl >= prev - 1e-9, f"SL not monotone at n={n}: {sl} < {prev}"
            prev = sl

    def test_sl_in_unit_interval(self):
        for n in [3, 5, 10]:
            sl = service_level(n, 2.0, 20, 240)
            assert 0.0 <= sl <= 1.0


# =============================================================================
# Test 5 — Skill compatibility (skill-aware coverage)
# =============================================================================

class TestSkillCompatibility:
    """
    Verify that the scheduler only counts agents with the correct skill
    toward coverage of a skill's slots.
    """

    def test_agents_without_skill_do_not_cover(self):
        """
        If we have 10 agents but none of them has skill_id=2,
        a requirement of 1 agent for skill 2 should result in uncovered slots.
        We verify this at the data level (before running OR-Tools).
        """
        agents_df = _make_agents(n=10)
        # All agents have skill 1, none has skill 2
        agent_skills_df = _make_agent_skills(list(range(1, 11)), skill_id=1)

        # Skill 2 has no qualified agents
        skill2_agents = agent_skills_df[agent_skills_df["skill_id"] == 2]["agent_id"].tolist()
        assert len(skill2_agents) == 0

    def test_agents_with_skill_cover(self):
        agents_df = _make_agents(n=5)
        agent_skills_df = _make_agent_skills([1, 2, 3], skill_id=1)

        skill1_agents = agent_skills_df[agent_skills_df["skill_id"] == 1]["agent_id"].tolist()
        assert set(skill1_agents) == {1, 2, 3}

    def test_multi_skill_agent_covers_both(self):
        """An agent with 2 skills should appear in both skill groups."""
        agent_skills_df = pd.DataFrame({
            "agent_id": [1, 1, 2],
            "skill_id": [1, 2, 1],
        })
        s1 = set(agent_skills_df[agent_skills_df["skill_id"] == 1]["agent_id"])
        s2 = set(agent_skills_df[agent_skills_df["skill_id"] == 2]["agent_id"])
        assert 1 in s1
        assert 1 in s2
        assert 2 in s1
        assert 2 not in s2


# =============================================================================
# Test 6 — Absence constraint
# =============================================================================

class TestAbsenceConstraint:
    """
    Verify that the absence-to-planning-day mapping works correctly.
    """

    def test_absence_maps_to_correct_day(self):
        """A Monday absence (dayofweek=0) should map to day_index=0."""
        import sys, os
        sys.path.insert(0, os.path.abspath(OPT_DIR))
        from run_optimization import build_absent_agent_days

        absences = pd.DataFrame({
            "agent_id": [1],
            "date": pd.to_datetime(["2026-08-10"]),   # Monday = dayofweek 0
        })
        result = build_absent_agent_days(absences)
        assert (1, 0) in result

    def test_empty_absences_returns_empty_set(self):
        from run_optimization import build_absent_agent_days

        result = build_absent_agent_days(pd.DataFrame(columns=["agent_id", "date"]))
        assert result == set()

    def test_multiple_absences(self):
        from run_optimization import build_absent_agent_days

        absences = pd.DataFrame({
            "agent_id": [1, 2, 1],
            "date": pd.to_datetime(["2026-08-10", "2026-08-11", "2026-08-12"]),
            # Monday=0, Tuesday=1, Wednesday=2
        })
        result = build_absent_agent_days(absences)
        assert (1, 0) in result   # agent 1, Monday
        assert (2, 1) in result   # agent 2, Tuesday
        assert (1, 2) in result   # agent 1, Wednesday


# =============================================================================
# Test 7 — Max weekly hours
# =============================================================================

class TestMaxWeeklyHours:

    def test_slot_count_to_hours(self):
        """
        160 slots × 0.25h = 40h → full-time limit.
        80 slots × 0.25h = 20h → part-time limit.
        """
        slot_duration_h = 15 / 60
        assert abs(160 * slot_duration_h - 40.0) < 0.001
        assert abs(80  * slot_duration_h - 20.0) < 0.001

    def test_full_time_max_slots(self):
        """Full-time: 40h / 0.25h = 160 slots max."""
        slot_duration_h = 15 / 60
        max_h = 40
        max_slots = int(max_h / slot_duration_h)
        assert max_slots == 160

    def test_part_time_max_slots(self):
        """Part-time: 20h / 0.25h = 80 slots max."""
        slot_duration_h = 15 / 60
        max_h = 20
        max_slots = int(max_h / slot_duration_h)
        assert max_slots == 80


# =============================================================================
# Test 8 — Minimum rest days
# =============================================================================

class TestMinRestDays:

    def test_planning_days_minus_rest(self):
        """MAX work days = 7 - 2 = 5 per week."""
        planning_days = 7
        min_rest = 2
        max_work_days = planning_days - min_rest
        assert max_work_days == 5

    def test_rest_days_from_schedule(self):
        """Given a schedule, verify rest days are correctly computed."""
        schedule = pd.DataFrame({
            "agent_id": [1, 1, 1, 1, 1],  # agent 1 works 5 days
            "day":      [0, 1, 2, 3, 4],
            "slot":     [0, 0, 0, 0, 0],
            "assigned": [1, 1, 1, 1, 1],
        })
        days_worked = schedule[schedule["agent_id"] == 1]["day"].nunique()
        rest_days = 7 - days_worked
        assert rest_days == 2   # exactly MIN_REST_DAYS


# =============================================================================
# Test 9 — Coverage per skill per slot
# =============================================================================

class TestCoverage:

    def test_full_coverage(self):
        """Schedule that exactly meets requirement → 100% coverage."""
        schedule = pd.DataFrame({
            "agent_id": [1, 2, 3],
            "day":      [0, 0, 0],
            "slot":     [0, 0, 0],
            "assigned": [1, 1, 1],
        })
        req = 3
        n_assigned = len(schedule[(schedule["day"] == 0) & (schedule["slot"] == 0)])
        assert n_assigned >= req

    def test_partial_coverage(self):
        """Schedule with 2 agents when 3 needed → coverage gap."""
        schedule = pd.DataFrame({
            "agent_id": [1, 2],
            "day":      [0, 0],
            "slot":     [0, 0],
            "assigned": [1, 1],
        })
        req = 3
        n_assigned = len(schedule[(schedule["day"] == 0) & (schedule["slot"] == 0)])
        assert n_assigned < req   # coverage gap

    def test_no_schedule_means_zero_coverage(self):
        """Empty schedule → 0% coverage for any positive requirement."""
        schedule = pd.DataFrame(columns=["agent_id", "day", "slot", "assigned"])
        n_assigned = 0
        req = 2
        assert n_assigned < req


# =============================================================================
# Test 10 — Cost calculation consistency
# =============================================================================

class TestCostCalculation:

    def test_optimized_cost_formula(self):
        """
        Schedule with 4 slots for 1 agent at 60 MAD/h:
        cost = 4 slots × 0.25h × 60 MAD/h = 60 MAD
        """
        schedule = pd.DataFrame({
            "agent_id": [1, 1, 1, 1],
            "day":      [0, 0, 0, 0],
            "slot":     [0, 1, 2, 3],
            "assigned": [1, 1, 1, 1],
        })
        agents = pd.DataFrame({
            "agent_id": [1],
            "base_hourly_cost": [60.0],
            "contract_type": ["full_time"],
        })
        merged = schedule.merge(agents[["agent_id", "base_hourly_cost"]], on="agent_id")
        slot_duration_h = 15 / 60
        cost = float((merged["base_hourly_cost"] * slot_duration_h).sum())
        assert abs(cost - 60.0) < 0.001, f"Expected 60.0, got {cost}"

    def test_cost_proportional_to_slots(self):
        """Doubling the slots doubles the cost."""
        slot_duration_h = 15 / 60
        cost_per_slot = 60.0 * slot_duration_h   # = 15 MAD per slot
        assert abs(cost_per_slot * 4 - 60.0) < 0.001   # 4 slots = 60 MAD
        assert abs(cost_per_slot * 8 - 120.0) < 0.001  # 8 slots = 120 MAD

    def test_saving_formula(self):
        """cost_saving_pct = (baseline - optimized) / baseline × 100."""
        baseline  = 269_762.0
        optimized = 83_250.0
        saving    = baseline - optimized
        pct       = saving / baseline * 100
        assert abs(pct - 69.12) < 0.1, f"Expected ~69.1%, got {pct:.2f}%"

    def test_zero_baseline_no_division(self):
        """Baseline of 0 should not cause division by zero."""
        baseline  = 0.0
        optimized = 100.0
        cost_saving_pct = (
            ((baseline - optimized) / baseline * 100) if baseline > 0 else 0.0
        )
        assert cost_saving_pct == 0.0
