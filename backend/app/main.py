from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import claims, health
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Covara API",
    description="AI-powered insurance claim readiness and intelligence.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(claims.router)
