from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import claims, health
import re

from app.config import get_settings
from app.core import persistence
from app.modules.evidence.router import router as evidence_router
from app.modules.intake.router import router as intake_router
from app.modules.packet.router import router as packet_router
from app.modules.pipeline.router import router as pipeline_router

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

@app.on_event("startup")
def restore_claims() -> None:
    persistence.load_all()
    persistence.expire_old()


_CLAIM_PATH = re.compile(r"^/claims/([0-9a-f]{32})(?:/|$)")


@app.middleware("http")
async def save_after_change(request, call_next):
    """Every request that changes a claim saves it (and removes expired ones when a new claim starts)."""
    response = await call_next(request)
    if request.method != "GET":
        m = _CLAIM_PATH.match(request.url.path)
        if m:
            persistence.snapshot(m.group(1))
        elif request.url.path == "/claims":
            persistence.expire_old()
            persistence.snapshot_all()
    return response


app.include_router(health.router)
app.include_router(claims.router)
app.include_router(intake_router)
app.include_router(pipeline_router)
app.include_router(evidence_router)
app.include_router(packet_router)
