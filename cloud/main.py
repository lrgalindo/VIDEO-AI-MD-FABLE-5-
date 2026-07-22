from contextlib import asynccontextmanager

from fastapi import FastAPI

from cloud.actions.router import router as actions_router
from cloud.actions.scheduler import start_action_engine_scheduler
from cloud.analytics.router import router as analytics_router
from cloud.auth.mfa import router as mfa_router
from cloud.auth.router import router as auth_router
from cloud.auth.superadmin import router as superadmin_router
from cloud.superadmin.breakglass import router as breakglass_router
from cloud.backoffice.router import router as backoffice_router
from cloud.backoffice.scheduler import start_revocation_scheduler
from cloud.copilot.router import router as copilot_router
from cloud.copilot.scheduler import start_audit_scheduler
from cloud.findings.router import router as findings_router
from cloud.lifecycle.router import router as lifecycle_router
from cloud.models.router import router as models_router
from cloud.telemetry.router import router as telemetry_router


@asynccontextmanager
async def _lifespan(application: FastAPI):
    start_revocation_scheduler()
    start_action_engine_scheduler()
    start_audit_scheduler()
    yield


app = FastAPI(title="Traxia Cloud API", version="0.1.0", lifespan=_lifespan)
app.include_router(actions_router)
app.include_router(analytics_router)
app.include_router(copilot_router)
app.include_router(findings_router)
app.include_router(auth_router)
app.include_router(mfa_router)
app.include_router(superadmin_router)
app.include_router(breakglass_router)
app.include_router(backoffice_router)
app.include_router(lifecycle_router)
app.include_router(models_router)
app.include_router(telemetry_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
