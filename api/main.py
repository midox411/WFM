from fastapi import FastAPI
from routers import forecast, attrition, optimization

app = FastAPI(
    title="WFM Intelligence Platform API",
    description="API REST exposant les prévisions (SARIMA), les risques (Attrition) et les plannings (OR-Tools)",
    version="1.0.0"
)

# Inclusion des différents modules (routers)
app.include_router(forecast.router, prefix="/api/v1/forecast", tags=["Forecasting"])
app.include_router(attrition.router, prefix="/api/v1/attrition", tags=["Attrition"])
app.include_router(optimization.router, prefix="/api/v1/optimization", tags=["Optimization"])

@app.get("/")
def read_root():
    return {"status": "ok", "message": "WFM API is running and ready."}