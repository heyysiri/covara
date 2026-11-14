from fastapi import APIRouter

from app.config import get_settings
from app.services.providers import provider_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "covara-backend",
        "version": "0.1.0",
        "environment": settings.app_env,
        "providers_configured": provider_status(),
    }
