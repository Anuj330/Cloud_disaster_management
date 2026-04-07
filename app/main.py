import logging
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from app.api import auth, backups, dr, observability, services
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging_config import configure_logging
from app.core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL, render_metrics
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
    initialize_region_state()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            default_admin = User(username="admin", password_hash=hash_password("admin12345"), role="admin")
            db.add(default_admin)
            db.commit()
            logger.info("Seeded default admin user", extra={"event": "bootstrap"})
    finally:
        db.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")
