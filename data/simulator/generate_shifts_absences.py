"""
Generates agent_shifts (baseline schedule), agent_breaks (short breaks + lunch),
and agent_absences.

Break placement is randomized per agent within safe windows, so lunch/breaks are
staggered rather than everyone hitting the same slot (e.g. not everyone at lunch
12:00-13:00). This is still a static, hand-built baseline schedule though - the
*dynamic* reallocation of breaks based on real-time absenteeism and call-volume
peaks is the job of the optimization module (week 2, Erlang C + OR-Tools), not
the simulator. The simulator's job is to produce a realistic "as-is" schedule
for the optimizer to later improve upon.
"""
import numpy as np
import pandas as pd
from datetime import timedelta

import config


def _active_date_range(hire_date, termination_date):
    start = max(hire_date, config.START_DATE)
    end = termination_date if pd.notna(termination_date) else config.END_DATE
    end = min(end, config.END_DATE)
    return start, end


def generate_shifts(agents: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """One row per agent per working day.
    Full-time: 5 days/week, alternates between two staggered patterns (8h-17h / 9h-18h).
    Part-time: 3 days/week (Mon/Wed/Fri), single 5h shift, no lunch.
    """
    rows = []
    for _, agent in agents.iterrows():
        start, end = _active_date_range(agent["hire_date"], agent["termination_date"])
        if start >= end:
            continue

        is_full_time = agent["contract_type"] == "full_time"
        # each agent keeps the same pattern for their whole tenure (not re-randomized daily)
        if is_full_time:
            start_hour, end_hour = config.FULL_TIME_SHIFT_PATTERNS[
                rng.integers(0, len(config.FULL_TIME_SHIFT_PATTERNS))
            ]
        else:
            start_hour = int(rng.choice([8, 9, 10]))
            end_hour = start_hour + config.PART_TIME_SHIFT_HOURS

        current = start
        while current <= end:
            dow = current.weekday()
            works_today = dow < 5 if is_full_time else dow in {0, 2, 4}
            if works_today:
                scheduled_start = pd.Timestamp(current) + pd.Timedelta(hours=start_hour)
                scheduled_end = pd.Timestamp(current) + pd.Timedelta(hours=end_hour)
                rows.append({
                    "agent_id": agent["agent_id"],
                    "shift_date": current,
                    "scheduled_start": scheduled_start,
                    "scheduled_end": scheduled_end,
                    "is_full_time": is_full_time,
                })
            current += timedelta(days=1)
    return pd.DataFrame(rows)


def generate_breaks(shifts: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """For each shift row, generates its break windows.
    Full-time (9h span): 2 short breaks + 1 lunch + 1 short break, placed
    sequentially with randomized gaps so agents don't all break at once.
    Part-time (5h span): 1 short break only.
    """
    rows = []
    short = config.SHORT_BREAK_MIN
    lunch = config.LUNCH_BREAK_MIN

    for row in shifts.itertuples():
        cursor = row.scheduled_start
        shift_end = row.scheduled_end

        if row.is_full_time:
            # gap ranges (minutes) tuned to fit an 8h worked / 9h span shift with margin
            cursor += pd.Timedelta(minutes=int(rng.integers(60, 120)))
            b1_start, b1_end = cursor, cursor + pd.Timedelta(minutes=short)
            cursor = b1_end + pd.Timedelta(minutes=int(rng.integers(60, 120)))

            lunch_start, lunch_end = cursor, cursor + pd.Timedelta(minutes=lunch)
            cursor = lunch_end + pd.Timedelta(minutes=int(rng.integers(45, 90)))

            b2_start, b2_end = cursor, cursor + pd.Timedelta(minutes=short)
            cursor = b2_end + pd.Timedelta(minutes=int(rng.integers(45, 90)))

            b3_start = min(cursor, shift_end - pd.Timedelta(minutes=short + 15))
            b3_end = b3_start + pd.Timedelta(minutes=short)

            rows += [
                {"agent_id": row.agent_id, "shift_date": row.shift_date,
                 "break_type": "short_break_1", "break_start": b1_start, "break_end": b1_end},
                {"agent_id": row.agent_id, "shift_date": row.shift_date,
                 "break_type": "lunch", "break_start": lunch_start, "break_end": lunch_end},
                {"agent_id": row.agent_id, "shift_date": row.shift_date,
                 "break_type": "short_break_2", "break_start": b2_start, "break_end": b2_end},
                {"agent_id": row.agent_id, "shift_date": row.shift_date,
                 "break_type": "short_break_3", "break_start": b3_start, "break_end": b3_end},
            ]
        else:
            b_start = cursor + pd.Timedelta(minutes=int(rng.integers(90, 150)))
            b_start = min(b_start, shift_end - pd.Timedelta(minutes=short + 15))
            b_end = b_start + pd.Timedelta(minutes=short)
            rows.append({
                "agent_id": row.agent_id, "shift_date": row.shift_date,
                "break_type": "short_break_1", "break_start": b_start, "break_end": b_end,
            })

    return pd.DataFrame(rows)


def generate_absences(agents: pd.DataFrame, shifts: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """A small fraction of scheduled shift-days become absences."""
    rows = []
    absence_types = np.array(["sick", "unplanned", "planned"])
    absence_probs = np.array([0.5, 0.3, 0.2])

    for agent_id, group in shifts.groupby("agent_id"):
        n_shifts = len(group)
        n_absences = int(rng.binomial(n_shifts, 0.035))  # ~3.5% absence rate
        if n_absences == 0:
            continue
        absent_days = group.sample(n=n_absences, random_state=int(rng.integers(0, 1_000_000)))
        for _, row in absent_days.iterrows():
            rows.append({
                "agent_id": agent_id,
                "date": row["shift_date"],
                "absence_type": rng.choice(absence_types, p=absence_probs),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import generate_agents as ga

    rng = np.random.default_rng(config.RANDOM_SEED)
    agents = ga.generate_agents(rng)

    shifts = generate_shifts(agents, rng)
    breaks = generate_breaks(shifts, rng)
    absences = generate_absences(agents, shifts, rng)

    print(f"Shifts: {len(shifts)} rows")
    print(shifts[["agent_id", "shift_date", "scheduled_start", "scheduled_end"]].head(4))
    print(shifts.groupby("is_full_time")["scheduled_start"].apply(lambda s: s.dt.hour.value_counts()))

    print(f"\nBreaks: {len(breaks)} rows")
    sample_agent, sample_date = shifts.iloc[0][["agent_id", "shift_date"]]
    print(breaks[(breaks.agent_id == sample_agent) & (breaks.shift_date == sample_date)])

    # sanity check: lunch start times should be spread out, not all at 12:00
    lunch_hours = breaks[breaks.break_type == "lunch"]["break_start"].dt.hour
    print("\nLunch start hour distribution:")
    print(lunch_hours.value_counts().sort_index())

    print(f"\nAbsences: {len(absences)} rows")