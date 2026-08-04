"""
Runs the full data simulation pipeline and writes all tables to Parquet files
in data/raw/. This is meant to be called either manually (for local dev/testing)
or from the Airflow ingestion DAG.
"""
import time
from pathlib import Path

import numpy as np

import config
import generate_agents as ga
import generate_shifts_absences as gsa
import generate_call_events as gce

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "raw"


def run(output_dir: Path = OUTPUT_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(config.RANDOM_SEED)

    t0 = time.time()

    skills = ga.generate_skills()
    agents = ga.generate_agents(rng)
    agent_skills = ga.generate_agent_skills(agents, rng)
    shifts = gsa.generate_shifts(agents, rng)
    breaks = gsa.generate_breaks(shifts, rng)
    absences = gsa.generate_absences(agents, shifts, rng)
    call_events = gce.generate_call_events(agents, agent_skills, absences, rng)

    tables = {
        "skills": skills,
        "agents": agents,
        "agent_skills": agent_skills,
        "agent_shifts": shifts,
        "agent_breaks": breaks,
        "agent_absences": absences,
        "call_events": call_events,
    }

    for name, df in tables.items():
        path = output_dir / f"{name}.parquet"
        df.to_parquet(path, index=False)
        print(f"  {name:<16} {len(df):>10,} rows -> {path}")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s. Output dir: {output_dir}")
    return tables


if __name__ == "__main__":
    run()