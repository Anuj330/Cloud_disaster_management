import logging
from app.core.config import get_settings
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)
settings = get_settings()


def _counter_key(namespace: str, identifier: str) -> str:
    return f"rate_limit:{namespace}:{identifier}"


def _lock_key(namespace: str, identifier: str) -> str:
    return f"rate_limit:{namespace}:{identifier}:lock"


def is_locked(namespace: str, identifier: str) -> bool:
    try:
        return bool(redis_client.exists(_lock_key(namespace, identifier)))
    except Exception:
        logger.exception("Rate limiter lock check failed")
        return False


def register_failure(namespace: str, identifier: str) -> None:
    key = _counter_key(namespace, identifier)
    lock_key = _lock_key(namespace, identifier)
    try:
        attempts = redis_client.incr(key)
        if attempts == 1:
            redis_client.expire(key, settings.auth_login_rate_window_seconds)
        if attempts >= settings.auth_login_rate_limit:
            redis_client.set(lock_key, "1", ex=settings.auth_login_lockout_seconds)
    except Exception:
        logger.exception("Rate limiter failure registration failed")


def register_success(namespace: str, identifier: str) -> None:
    key = _counter_key(namespace, identifier)
    lock_key = _lock_key(namespace, identifier)
    try:
        redis_client.delete(key, lock_key)
    except Exception:
        logger.exception("Rate limiter success reset failed")
