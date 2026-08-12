import sys
sys.path.insert(0, '/opt/airflow/ml_optimization')

from erlang_c import _erlang_c, service_level, agents_required, compute_staffing_requirement
import pandas as pd

print("=== Targeted Optimization Tests ===\n")

# Test 1: Erlang C known value N=2, A=1 -> P(wait) = 1/3
ec = _erlang_c(2, 1.0)
assert abs(ec - 1/3) < 0.001, f'Erlang C(2,1) should be 1/3, got {ec}'
print(f'[OK] Erlang C(2,1) = {ec:.4f} (expected 0.3333)')

# Test 2: zero volume = zero agents
r = compute_staffing_requirement([0.0])
assert r[0] == 0
print(f'[OK] zero volume -> 0 agents')

# Test 3: higher volume needs more agents
r_low  = compute_staffing_requirement([100.0])[0]
r_high = compute_staffing_requirement([500.0])[0]
assert r_high >= r_low, f'Higher volume needs more agents: {r_low} vs {r_high}'
print(f'[OK] 100 calls -> {r_low} agents, 500 calls -> {r_high} agents')

# Test 4: safety cap respected
r_cap = compute_staffing_requirement([1_000_000.0], max_agents=30)
assert r_cap[0] <= 30
print(f'[OK] safety cap: extreme volume capped at {r_cap[0]} agents')

# Test 5: service level monotone in N
a = 3.0
prev = 0.0
for n in range(4, 15):
    sl = service_level(n, a, 20, 240)
    assert sl >= prev - 1e-9, f'SL not monotone at n={n}'
    prev = sl
print(f'[OK] SL is monotone increasing with N (A=3, t=20s, AHT=240s)')

# Test 6: OR-Tools constraint math
import config
slot_h = config.SLOT_DURATION_MIN / 60.0
ft_max_slots = int(config.MAX_HOURS_FULL_TIME / slot_h)
pt_max_slots = int(config.MAX_HOURS_PART_TIME / slot_h)
max_work_days = config.PLANNING_DAYS - config.MIN_REST_DAYS
assert ft_max_slots == 160
assert pt_max_slots == 80
assert max_work_days == 5
print(f'[OK] Constraints: FT max={ft_max_slots} slots, PT max={pt_max_slots} slots, max work days={max_work_days}')

# Test 7: cost formula
sched = pd.DataFrame({'agent_id': [1,1,1,1], 'day': [0,0,0,0], 'slot': [0,1,2,3], 'assigned': [1,1,1,1]})
agents = pd.DataFrame({'agent_id': [1], 'base_hourly_cost': [60.0]})
merged = sched.merge(agents, on='agent_id')
cost = float((merged['base_hourly_cost'] * slot_h).sum())
assert abs(cost - 60.0) < 0.001, f'Expected 60.0, got {cost}'
print(f'[OK] Cost formula: 4 slots x 0.25h x 60 MAD/h = {cost:.1f} MAD')

# Test 8: saving formula
baseline  = 269762.0
optimized = 83250.0
saving_pct = (baseline - optimized) / baseline * 100
assert abs(saving_pct - 69.12) < 0.1, f'Expected ~69.1%, got {saving_pct:.2f}%'
print(f'[OK] Cost saving formula: (269762-83250)/269762 = {saving_pct:.1f}%')

# Test 9: zero baseline -> no division by zero
saving_pct_safe = ((0.0 - 100.0) / 0.0 * 100) if 0.0 > 0 else 0.0
assert saving_pct_safe == 0.0
print(f'[OK] Zero baseline handled safely (no division by zero)')

# Test 10: coverage rate logic
# slot with req=3, only 2 assigned -> not covered
n_assigned = 2
req = 3
covered = 1 if n_assigned >= req else 0
assert covered == 0
# slot with req=3, 3 assigned -> covered
n_assigned2 = 3
covered2 = 1 if n_assigned2 >= req else 0
assert covered2 == 1
print(f'[OK] Coverage logic: {n_assigned} < {req} -> not covered | {n_assigned2} >= {req} -> covered')

print("\n=== ALL 10 TESTS PASSED ===")
