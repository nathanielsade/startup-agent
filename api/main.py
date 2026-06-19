from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health

app = FastAPI(title="Startup Job Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
