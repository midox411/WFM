from fastapi import FastAPI
from routers import forecast, attrition, optimization, simulator, monitoring

app = FastAPI(
    title="WFM Intelligence Platform API",
    description="API REST exposant les prévisions (SARIMA), les risques (Attrition), les plannings (OR-Tools), le simulateur What-if et le Drift Monitoring",
    version="1.0.0"
)

# Inclusion des différents modules (routers)
app.include_router(forecast.router, prefix="/api/v1/forecast", tags=["Forecasting"])
app.include_router(attrition.router, prefix="/api/v1/attrition", tags=["Attrition"])
app.include_router(optimization.router, prefix="/api/v1/optimization", tags=["Optimization"])
app.include_router(simulator.router, prefix="/api/v1/simulator", tags=["Simulator"])
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["Drift Monitoring"])

@app.get("/")
def read_root():
    return {"status": "ok", "message": "WFM API is running and ready."}