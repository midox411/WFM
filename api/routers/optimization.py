import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter()

SCHEDULE_PATH = "/opt/wfm_data/processed/optimized_schedule.csv"

@router.get("/schedule")
def get_optimized_schedule(day: int = None, agent_id: int = None):
    """Expose le planning optimal généré par le DAG d'optimisation (OR-Tools)"""
    try:
        df = pd.read_csv(SCHEDULE_PATH)
        
        # Filtres optionnels
        if day is not None:
            df = df[df["day"] == day]
        if agent_id is not None:
            df = df[df["agent_id"] == agent_id]
            
        return {"total_shifts_slots": len(df), "schedule": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Planning non trouvé. Avez-vous lancé le DAG d'optimisation ? Erreur: {str(e)}"
        )