# Production Readiness Checklist

Status legend:
- `[x]` implemented in this repo
- `[ ]` pending

## Security

- [x] Remove hardcoded default admin credentials from startup flow.
- [x] Require explicit admin bootstrap via environment (`BOOTSTRAP_INITIAL_ADMIN`).
- [x] Enforce stronger secret key usage on startup (`SECRET_KEY` length and placeholder checks) unless `ALLOW_INSECURE_DEV_DEFAULTS=true`.
- [x] Add auth brute-force protection on `/api/v1/auth/token` (rate-limit/lockout by `username + client IP` in Redis).
- [x] Restrict user role creation to known roles (`admin`, `operator`).
- [ ] Add refresh token flow and token revocation list.
- [ ] Implement audit log signing and tamper-evident storage.

## Reliability

- [x] Add liveness endpoint (`/health/live`).
- [x] Add readiness endpoint (`/health/ready`) with DB and Redis dependency checks.
- [x] Return HTTP `503` for readiness failure.
- [x] Add distributed lock deduplication for recovery workflows.
- [x] Add distributed lock deduplication for scheduled backups.
- [x] Make locking fail open when Redis lock operations fail so critical tasks still run.
- [ ] Add idempotency keys for manual failover and backup endpoints.
- [ ] Add dead-letter queue strategy for failed Celery tasks.

## Data Protection

- [ ] Replace local object store simulation with managed multi-region object storage.
- [ ] Enable immutable backups and retention policies.
- [ ] Add periodic restore drills with pass/fail reporting.

## Observability and Operations

- [ ] Add OpenTelemetry traces with trace IDs in logs.
- [ ] Add alerting for failed backups, workflow failures, and dependency readiness failures.
- [ ] Publish SLOs for uptime, backup success, recovery success, and failover time.
- [ ] Add incident runbooks and game-day automation.

## Delivery Controls

- [ ] Add CI pipeline with unit/integration tests.
- [ ] Add dependency + container vulnerability scans.
- [ ] Add migration safety checks and rollback drills.
