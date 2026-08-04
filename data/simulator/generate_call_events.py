"""
Generates call_events: the large fact table (~3.65M rows for 12 months x ~10k calls/day).
Vectorized with numpy/pandas to keep generation time reasonable.

Approach:
  1. For each day, compute the expected call volume (base * dow_weight * month_weight * noise)
  2. Split that volume across open hours using HOURLY_WEIGHTS (multinomial draw)
  3. For each day, generate individual timestamps uniformly within their hour,
     vectorized skill assignment, vectorized disposition assignment
  4. Once per day (not per call): compute the set of eligible agents per skill
     (active on that date AND not absent that date). Then, per skill, vectorized
     rng.choice() assigns agents to all of that day's answered/transferred calls
     for that skill in one shot.
  5. Handle time is derived per assigned agent's seniority via a vectorized map.
"""
import numpy as np
import pandas as pd

import config


def _daily_volumes(rng: np.random.Generator) -> pd.DataFrame:
    dates = pd.date_range(config.START_DATE, config.END_DATE, freq="D")
    dow_w = np.array([config.DOW_WEIGHTS[d.weekday()] for d in dates])
    month_w = np.array([config.MONTH_WEIGHTS[d.month] for d in dates])
    holiday_w = np.array([config.HOLIDAYS.get(d.date(), 1.0) for d in dates])
    noise = rng.normal(1.0, 0.06, size=len(dates))
    expected = config.TARGET_DAILY_CALLS * dow_w * month_w * holiday_w * noise
    expected = np.clip(expected, a_min=20, a_max=None)
    volumes = rng.poisson(expected)
    return pd.DataFrame({"date": dates, "volume": volumes})


def _hour_distribution():
    hours = np.array(sorted(config.HOURLY_WEIGHTS.keys()))
    weights = np.array([config.HOURLY_WEIGHTS[h] for h in hours])
    return hours, weights / weights.sum()


def _skill_to_agents_map(agent_skills: pd.DataFrame):
    return {
        skill_id: group["agent_id"].to_numpy()
        for skill_id, group in agent_skills.groupby("skill_id")
    }


def generate_call_events(
    agents: pd.DataFrame,
    agent_skills: pd.DataFrame,
    absences: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    skill_ids = np.array([s["skill_id"] for s in config.SKILLS])
    skill_weights = np.array([s["weight"] for s in config.SKILLS])
    skill_weights = skill_weights / skill_weights.sum()

    hours, hour_probs = _hour_distribution()
    skill_to_agents = _skill_to_agents_map(agent_skills)

    hire_dates = agents.set_index("agent_id")["hire_date"]
    term_dates = agents.set_index("agent_id")["termination_date"]
    seniority_map = agents.set_index("agent_id")["seniority_level"].to_dict()

    absences_by_date = {}
    if len(absences):
        for d, group in absences.groupby(absences["date"]):
            key = pd.Timestamp(d).date()
            absences_by_date[key] = set(group["agent_id"].tolist())

    daily = _daily_volumes(rng)

    event_frames = []
    event_id_counter = 1

    for date_ts, day_volume in zip(daily["date"], daily["volume"]):
        day_volume = int(day_volume)
        if day_volume == 0:
            continue
        the_date = date_ts.date()

        hour_counts = rng.multinomial(day_volume, hour_probs)
        rep_hours = np.repeat(hours, hour_counts)
        seconds_offsets = rng.integers(0, 3600, size=day_volume)
        timestamps = pd.Timestamp(the_date) + pd.to_timedelta(rep_hours, unit="h") + \
            pd.to_timedelta(seconds_offsets, unit="s")

        call_skills = rng.choice(skill_ids, size=day_volume, p=skill_weights)

        is_peak = np.isin(rep_hours, list(config.PEAK_HOURS))
        abandon_p = np.where(is_peak, config.BASE_ABANDON_RATE * config.PEAK_ABANDON_MULTIPLIER,
                              config.BASE_ABANDON_RATE)
        transfer_p = np.full(day_volume, config.BASE_TRANSFER_RATE)
        answer_p = np.clip(1 - abandon_p - transfer_p, 0.01, None)
        totals = answer_p + abandon_p + transfer_p
        answer_p, abandon_p, transfer_p = answer_p / totals, abandon_p / totals, transfer_p / totals

        rand_vals = rng.random(day_volume)
        dispositions = np.where(
            rand_vals < answer_p, "answered",
            np.where(rand_vals < answer_p + abandon_p, "abandoned", "transferred")
        )

        wait_mean = np.where(is_peak, 45, 20)
        wait_times = rng.exponential(wait_mean).astype(int)

        agent_ids = np.full(day_volume, np.nan)
        handle_times = np.full(day_volume, np.nan)

        absent_today = absences_by_date.get(the_date, set())

        for skill_id in skill_ids:
            candidates = skill_to_agents.get(skill_id, np.array([]))
            if len(candidates) == 0:
                continue
            eligible = [
                a for a in candidates
                if hire_dates[a] <= the_date
                and (pd.isna(term_dates[a]) or term_dates[a] >= the_date)
                and a not in absent_today
            ]
            if not eligible:
                continue
            eligible = np.array(eligible)

            wants_agent = (call_skills == skill_id) & np.isin(dispositions, ["answered", "transferred"])
            n_needed = wants_agent.sum()
            if n_needed == 0:
                continue

            chosen = rng.choice(eligible, size=n_needed, replace=True)
            agent_ids[wants_agent] = chosen

            chosen_seniority = np.array([seniority_map[a] for a in chosen])
            base_mean = np.where(chosen_seniority == "senior", 240, 340)
            handle_times[wants_agent] = np.maximum(
                30, rng.lognormal(np.log(base_mean), 0.35)
            ).astype(int)

        no_agent_found = (dispositions != "abandoned") & np.isnan(agent_ids) & \
            np.isin(dispositions, ["answered", "transferred"])
        dispositions = np.where(no_agent_found, "abandoned", dispositions)

        n = day_volume
        event_ids = np.arange(event_id_counter, event_id_counter + n)
        event_id_counter += n

        event_frames.append(pd.DataFrame({
            "event_id": event_ids,
            "timestamp": timestamps,
            "skill_id": call_skills,
            "agent_id": agent_ids,
            "wait_time_sec": wait_times,
            "handle_time_sec": handle_times,
            "disposition": dispositions,
        }))

    df = pd.concat(event_frames, ignore_index=True)
    df["channel"] = "call"
    df["agent_id"] = df["agent_id"].astype("Int64")
    return df


if __name__ == "__main__":
    import time
    import generate_agents as ga
    import generate_shifts_absences as gsa

    rng = np.random.default_rng(config.RANDOM_SEED)
    agents = ga.generate_agents(rng)
    agent_skills = ga.generate_agent_skills(agents, rng)
    shifts = gsa.generate_shifts(agents, rng)
    absences = gsa.generate_absences(agents, shifts, rng)

    t0 = time.time()
    call_events = generate_call_events(agents, agent_skills, absences, rng)
    elapsed = time.time() - t0

    print(f"Generated {len(call_events):,} call events in {elapsed:.1f}s")
    print(call_events.head())
    print(call_events["disposition"].value_counts(normalize=True))
    print(f"Unassigned agent_id rate: {call_events['agent_id'].isna().mean():.3f}")