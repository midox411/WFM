"""
Erlang C staffing calculator.
"""
import math
import numpy as np


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
    return float(np.clip(ec, 0.0, 1.0))


def service_level(n: int, a: float, answer_time_sec: float, aht_sec: float) -> float:
    if n <= 0:
        return 0.0
    ec = _erlang_c(n, a)
    if a >= n:
        return 0.0
    exponent = -(n - a) * answer_time_sec / aht_sec
    sl = 1.0 - ec * math.exp(exponent)
    return float(np.clip(sl, 0.0, 1.0))


def agents_required(
    call_volume: float,
    slot_min: int,
    aht_sec: float,
    target_sl: float,
    answer_time_sec: float,
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


def compute_staffing_requirement(
    slots_volume: list,
    slot_min: int = 15,
    aht_sec: float = 240,
    target_sl: float = 0.80,
    answer_time_sec: float = 20,
    max_agents: int = 60,
) -> list:
    return [
        agents_required(v, slot_min, aht_sec, target_sl, answer_time_sec, max_agents)
        for v in slots_volume
    ]