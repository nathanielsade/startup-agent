from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import cv, health, llm_config, preferences, rate, results, run

app = FastAPI(title="Startup Job Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(cv.router, prefix="/api")
app.include_router(run.router, prefix="/api")
app.include_router(results.router, prefix="/api")
app.include_router(preferences.router, prefix="/api")
app.include_router(rate.router, prefix="/api")
app.include_router(llm_config.router, prefix="/api")
