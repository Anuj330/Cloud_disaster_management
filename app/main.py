import logging
import time
from sqlalchemy import text
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as RawResponse
from app.api import auth, backups, dr, observability, services
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.logging_config import configure_logging
from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL, render_metrics
from app.core.redis_client import redis_client
from app.core.security import hash_password
from app.models.entities import User
from app.services.failover_service import initialize_region_state

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(services.router, prefix=settings.api_prefix)
app.include_router(dr.router, prefix=settings.api_prefix)
app.include_router(backups.router, prefix=settings.api_prefix)
app.include_router(observability.router, prefix=settings.api_prefix)


@app.middleware("http")
async def prometheus_http_metrics(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    method = request.method
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status_code=str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(elapsed)
    return response


@app.on_event("startup")
def startup_event() -> None:
    if not settings.allow_insecure_dev_defaults:
        insecure_defaults = {
            "change-me",
            "replace-with-a-long-random-secret-key",
            "replace-with-secure-random-key",
        }
        if settings.secret_key in insecure_defaults or len(settings.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be set to a strong random value (32+ chars).")

    initialize_region_state()

    if settings.bootstrap_initial_admin:
        if not settings.initial_admin_username or not settings.initial_admin_password:
            raise RuntimeError(
                "INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD are required when BOOTSTRAP_INITIAL_ADMIN=true."
            )
        if len(settings.initial_admin_password) < 12:
            raise RuntimeError("INITIAL_ADMIN_PASSWORD must be at least 12 characters.")

        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.username == settings.initial_admin_username).first()
            if not admin:
                bootstrap_admin = User(
                    username=settings.initial_admin_username,
                    password_hash=hash_password(settings.initial_admin_password),
                    role="admin",
                )
                db.add(bootstrap_admin)
                db.commit()
                logger.info("Seeded bootstrap admin user", extra={"event": "bootstrap"})
        finally:
            db.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "live"}


@app.get("/health/live")
def health_live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(response: Response) -> dict:
    checks = {"database": "ok", "redis": "ok"}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "failed"

    try:
        redis_client.ping()
    except Exception:
        checks["redis"] = "failed"

    if any(value != "ok" for value in checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "checks": checks}
    return {"status": "ok", "checks": checks}


@app.get("/metrics")
def metrics() -> RawResponse:
    return RawResponse(content=render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")
