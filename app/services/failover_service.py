import logging
from app.core.config import get_settings
from app.core.metrics import FAILOVER_EVENTS_TOTAL, set_active_region
from app.core.redis_client import redis_client
from app.models.entities import FailoverEvent

logger = logging.getLogger(__name__)
settings = get_settings()

ACTIVE_REGION_KEY = "dr:active_region"
STANDBY_REGION_KEY = "dr:standby_region"


def initialize_region_state() -> None:
    if not redis_client.get(ACTIVE_REGION_KEY):
        redis_client.set(ACTIVE_REGION_KEY, settings.primary_region)
    if not redis_client.get(STANDBY_REGION_KEY):
        redis_client.set(STANDBY_REGION_KEY, settings.secondary_region)
    set_active_region(redis_client.get(ACTIVE_REGION_KEY), [settings.primary_region, settings.secondary_region])


def get_region_state() -> dict[str, str]:
    initialize_region_state()
    return {
        "active_region": redis_client.get(ACTIVE_REGION_KEY),
        "standby_region": redis_client.get(STANDBY_REGION_KEY),
    }


def trigger_failover(db, reason: str) -> dict[str, str]:
    state = get_region_state()
    from_region = state["active_region"]
    to_region = state["standby_region"]

    redis_client.set(ACTIVE_REGION_KEY, to_region)
    redis_client.set(STANDBY_REGION_KEY, from_region)
    set_active_region(to_region, [settings.primary_region, settings.secondary_region])

    event = FailoverEvent(from_region=from_region, to_region=to_region, reason=reason)
    db.add(event)
    db.commit()
    FAILOVER_EVENTS_TOTAL.inc()

    logger.warning(
        "Failover triggered",
        extra={
            "event": "failover",
            "region": from_region,
            "extra_data": {"to_region": to_region, "reason": reason},
        },
    )

    return {"from_region": from_region, "to_region": to_region, "reason": reason}
