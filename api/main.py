from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from startup_agent.config.settings import Settings

from api.routes import (
    cv, health, llm_config, preferences, profile, rate, results, run, tracking,
)

app = FastAPI(title="Startup Job Agent")

_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:5174", "http://127.0.0.1:5174"]
# Deploy: set CORS_ORIGINS to the frontend origin(s), comma-separated.
_extra = [o.strip() for o in Settings().cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEV_ORIGINS + _extra,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(cv.router, prefix="/api")
app.include_router(run.router, prefix="/api")
app.include_router(results.router, prefix="/api")
app.include_router(preferences.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(rate.router, prefix="/api")
app.include_router(llm_config.router, prefix="/api")
app.include_router(tracking.router, prefix="/api")
