"""
Generates the static reference tables: agents, skills, agent_skills.
"""
import numpy as np
import pandas as pd
from faker import Faker
from datetime import timedelta

import config

fake = Faker()


def generate_skills() -> pd.DataFrame:
    return pd.DataFrame(
        [{"skill_id": s["skill_id"], "skill_name": s["skill_name"]} for s in config.SKILLS]
    )


def generate_agents(rng: np.random.Generator) -> pd.DataFrame:
    n = config.NUM_AGENTS
    Faker.seed(config.RANDOM_SEED)

    # Hire dates spread over the last 1 to 5 years before the simulation start
    days_before_start = rng.integers(365, 5 * 365, size=n)
    hire_dates = [config.START_DATE - timedelta(days=int(d)) for d in days_before_start]

    # Seniority correlates with tenure: hired > 2 years before start => more likely senior
    seniority = []
    for hd in hire_dates:
        tenure_days = (config.START_DATE - hd).days
        p_senior = min(0.85, 0.15 + tenure_days / (5 * 365) * 0.7)
        seniority.append("senior" if rng.random() < p_senior else "junior")

    contract_type = rng.choice(
        ["full_time", "part_time"], size=n, p=[0.85, 0.15]
    )

    # Attrition: churn risk is weighted by plausible HR factors instead of
    # picked uniformly at random - otherwise there is literally no real signal
    # for an attrition model to learn (any "good" metric would only reflect
    # data leakage, not a genuine pattern). Junior agents, part-time contracts,
    # and short tenure-at-hire all raise the odds of leaving, with noise on
    # top so it stays a probabilistic pattern, not a deterministic rule.
    tenure_at_start_days = np.array([(config.START_DATE - hd).days for hd in hire_dates])
    short_tenure_factor = np.clip(2.2 - tenure_at_start_days / (2 * 365), 0.6, 2.2)

    risk_weight = np.ones(n)
    risk_weight *= np.where(np.array(seniority) == "junior", 1.8, 0.8)
    risk_weight *= np.where(contract_type == "part_time", 2.4, 1.0)
    risk_weight *= short_tenure_factor
    risk_weight *= rng.uniform(0.7, 1.3, size=n)  # keep it probabilistic, not deterministic
    risk_weight /= risk_weight.sum()

    n_terminated = int(round(n * config.ATTRITION_RATE))
    terminated_idx = set(rng.choice(n, size=n_terminated, replace=False, p=risk_weight).tolist())

    window_days = (config.END_DATE - config.START_DATE).days
    status, termination_dates = [], []
    for i in range(n):
        if i in terminated_idx:
            # termination happens sometime after month 2 of the sim, so there's
            # enough history before departure to be useful for the attrition model
            offset = int(rng.integers(60, window_days))
            status.append("terminated")
            termination_dates.append(config.START_DATE + timedelta(days=offset))
        else:
            status.append("active")
            termination_dates.append(pd.NaT)

    team = rng.choice(config.TEAMS, size=n)

    base_cost = [
        round(rng.uniform(45, 60), 2) if s == "junior" else round(rng.uniform(60, 85), 2)
        for s in seniority
    ]

    agents = pd.DataFrame({
        "agent_id": np.arange(1, n + 1),
        "first_name": [fake.first_name() for _ in range(n)],
        "last_name": [fake.last_name() for _ in range(n)],
        "hire_date": hire_dates,
        "termination_date": termination_dates,
        "status": status,
        "site": config.SITE,
        "team": team,
        "contract_type": contract_type,
        "seniority_level": seniority,
        "base_hourly_cost": base_cost,
    })
    return agents


def generate_agent_skills(agents: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Each agent is assigned 1-2 skills. Weighted so 'Customer Service' is the
    most common primary skill, matching the relative demand per queue."""
    skill_ids = [s["skill_id"] for s in config.SKILLS]
    weights = np.array([s["weight"] for s in config.SKILLS])
    weights = weights / weights.sum()

    rows = []
    for agent_id, seniority in zip(agents["agent_id"], agents["seniority_level"]):
        n_skills = 2 if rng.random() < 0.35 else 1
        chosen = rng.choice(skill_ids, size=n_skills, replace=False, p=weights)
        for skill_id in chosen:
            # proficiency mostly follows seniority, with a bit of noise
            proficiency = seniority if rng.random() < 0.8 else rng.choice(["junior", "senior"])
            rows.append({"agent_id": agent_id, "skill_id": int(skill_id), "proficiency_level": proficiency})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    rng = np.random.default_rng(config.RANDOM_SEED)
    skills = generate_skills()
    agents = generate_agents(rng)
    agent_skills = generate_agent_skills(agents, rng)

    print(skills)
    print(agents.head())
    print(f"Terminated: {(agents['status'] == 'terminated').sum()} / {len(agents)}")
    print(agent_skills.head())
    print(f"agent_skills rows: {len(agent_skills)}")