import logging
import time
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.metrics import set_service_status
from app.models.entities import Service
from app.services.failover_service import get_region_state, trigger_failover

logger = logging.getLogger(__name__)
settings = get_settings()


def _circuit_allows_request(service: Service) -> bool:
    if service.circuit_state != "OPEN":
        return True
    if not service.circuit_opened_at:
        return False
    reset_after = service.circuit_opened_at + timedelta(seconds=settings.circuit_breaker_reset_timeout_seconds)
    if datetime.utcnow() >= reset_after:
        service.circuit_state = "HALF_OPEN"
        return True
    return False


def _request_with_retry(url: str) -> tuple[bool, float]:
    backoff = settings.health_check_retry_backoff_seconds
    for attempt in range(settings.health_check_retry_count):
        start = time.perf_counter()
        try:
            response = httpx.get(url, timeout=settings.health_check_timeout_seconds)
            latency_ms = (time.perf_counter() - start) * 1000
            if response.status_code < 500:
                payload = response.json() if "application/json" in response.headers.get("content-type", "") else {}
                if payload.get("status") != "down":
                    return True, latency_ms
        except httpx.RequestError:
            latency_ms = (time.perf_counter() - start) * 1000
        except ValueError:
            pass

        if attempt < settings.health_check_retry_count - 1:
            time.sleep(backoff)
            backoff *= 2
    return False, latency_ms


def evaluate_service_health(db: Session, service: Service) -> Service:
    if not _circuit_allows_request(service):
        service.status = "DOWN"
        db.commit()
        return service

    ok, latency_ms = _request_with_retry(service.url)
    service.last_heartbeat = datetime.utcnow()

    if ok:
        service.consecutive_failures = 0
        service.circuit_state = "CLOSED"
        service.circuit_opened_at = None
        service.status = "DEGRADED" if latency_ms > 1500 else "HEALTHY"
    else:
        service.consecutive_failures += 1
        service.status = "DOWN"
        if service.consecutive_failures >= settings.circuit_breaker_failure_threshold:
            service.circuit_state = "OPEN"
            service.circuit_opened_at = datetime.utcnow()

    db.commit()
    db.refresh(service)
    set_service_status(service.name, service.region, service.status)

    logger.info(
        "Health check evaluated",
        extra={
            "event": "health_check",
            "service": service.name,
            "region": service.region,
            "extra_data": {
                "status": service.status,
                "latency_ms": round(latency_ms, 2),
                "circuit": service.circuit_state,
            },
        },
    )
    return service


def run_all_health_checks(db: Session) -> dict:
    services = db.query(Service).all()
    down_in_active_region = []

    state = get_region_state()
    active_region = state["active_region"]

    for service in services:
        updated = evaluate_service_health(db, service)
        if updated.region == active_region and updated.status == "DOWN" and updated.is_primary:
            down_in_active_region.append(updated.name)

    failover_event = None
    if down_in_active_region:
        failover_event = trigger_failover(db, reason=f"Primary services down: {', '.join(down_in_active_region)}")

    return {
        "services_checked": len(services),
        "down_primary_services": down_in_active_region,
        "failover": failover_event,
    }
