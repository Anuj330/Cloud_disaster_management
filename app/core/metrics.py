from prometheus_client import Counter, Gauge, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "dr_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "dr_http_request_duration_seconds",
    "HTTP request latency seconds",
    ["method", "path"],
)

FAILOVER_EVENTS_TOTAL = Counter("dr_failover_events_total", "Total failover events")
BACKUPS_CREATED_TOTAL = Counter("dr_backups_created_total", "Total backup snapshots created")
RECOVERY_WORKFLOWS_TOTAL = Counter("dr_recovery_workflows_total", "Total recovery workflows executed")

ACTIVE_REGION_GAUGE = Gauge("dr_active_region", "Active region represented as binary label", ["region"])
SERVICE_STATUS_GAUGE = Gauge("dr_service_status", "Service status by region and service", ["service", "region", "status"])


SERVICE_STATUS_VALUES = ["HEALTHY", "DEGRADED", "DOWN"]


def render_metrics() -> bytes:
    return generate_latest()


def set_active_region(region: str, all_regions: list[str]) -> None:
    for candidate in all_regions:
        ACTIVE_REGION_GAUGE.labels(region=candidate).set(1 if candidate == region else 0)


def set_service_status(service: str, region: str, status: str) -> None:
    for candidate in SERVICE_STATUS_VALUES:
        SERVICE_STATUS_GAUGE.labels(service=service, region=region, status=candidate).set(1 if candidate == status else 0)
