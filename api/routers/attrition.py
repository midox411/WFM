import os
from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine
import pandas as pd

router = APIRouter()

def get_engine():
    user = os.environ.get("POSTGRES_USER", "admin")
    pwd = os.environ.get("POSTGRES_PASSWORD", "admin")
    db = os.environ.get("POSTGRES_APP_DB", "wfm_app")
    return create_engine(f"postgresql+psycopg2://{user}:{pwd}@postgres:5432/{db}")

@router.get("/agents")
def get_agents_status():
    """Récupère le statut des agents depuis la base de données Postgres"""
    try:
        engine = get_engine()
        query = """
            SELECT agent_id, status, contract_type, seniority_level, base_hourly_cost 
            FROM agents 
            WHERE status = 'active'
        """
        df = pd.read_sql(query, engine)
        return {"active_agents": len(df), "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))