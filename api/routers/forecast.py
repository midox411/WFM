import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter()

VOLUME_PATH = "/opt/wfm_data/processed/volume_15min"

@router.get("/intraday")
def get_intraday_volumes(limit: int = 100):
    """Récupère le profil des volumes 15 minutes (aggrégé par Spark)"""
    try:
        df = pd.read_parquet(VOLUME_PATH)
        # Transformation pour l'API
        if "interval_15min" in df.columns:
            df["interval_15min"] = df["interval_15min"].astype(str)
        result = df.head(limit).to_dict(orient="records")
        return {"count": len(result), "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture Parquet: {str(e)}")