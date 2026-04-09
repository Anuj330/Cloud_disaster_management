# Cloud Disaster Management System (FastAPI)

A production-style disaster recovery platform simulation for cloud-native applications.

## Implemented Capabilities

- Multi-service registry with region and priority
- Active/standby multi-region failover state in Redis
- Automated health monitoring with retry + exponential backoff
- Circuit breaker per service (CLOSED/HALF_OPEN/OPEN)
- Manual + scheduled backups with versioning and object-store simulation
- Recovery workflow automation (`detect -> failover -> restore -> recovered`)
- RTO/RPO metrics tracking
- JWT auth and role-based access (`admin`, `operator`)
- Structured JSON logs for operational visibility
- Prometheus metrics endpoint (`/metrics`)
- React dashboard with live polling and failover timeline
- Alembic migrations and DB readiness wait logic for safer startup

## Architecture

- `FastAPI`: control plane and APIs
- `PostgreSQL`: persistent metadata (services, events, backups, workflows)
- `Redis`: failover region state + Celery broker/backend
- `Celery Worker/Beat`: scheduled health checks, backups, async recovery workflows
- `Alembic`: schema versioning and migration lifecycle
- `React (Vite)`: real-time DR dashboard
- Mock services for region A and B to simulate failures

## Project Structure

```text
app/
 ├── main.py
 ├── api/
 ├── core/
 ├── models/
 ├── services/
 ├── workers/
 ├── utils/
alembic/
 ├── env.py
 └── versions/
dashboard/
 └── src/
```

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

For local development, `.env.example` enables:
- `ALLOW_INSECURE_DEV_DEFAULTS=true`
- `BOOTSTRAP_INITIAL_ADMIN=true` (with configurable `INITIAL_ADMIN_*` values)

This starts:

- API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- Prometheus metrics: `http://localhost:8000/metrics`
- Dashboard: `http://localhost:5173`

Default admin account:

- username/password are created only when `BOOTSTRAP_INITIAL_ADMIN=true`
- configure `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` in `.env`

## Migration Workflow

The `api` service runs the following at startup:

1. Wait for PostgreSQL readiness (`scripts/wait_for_db.py`)
2. Apply migrations (`alembic upgrade head`)
3. Start FastAPI

Manual migration commands:

```bash
alembic upgrade head
alembic downgrade -1
```

## API Workflow (Real DR Scenario)

### 1. Get JWT token

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<admin_user>&password=<admin_password>"
```

Set token:

```bash
export TOKEN="<access_token>"
```

### 2. Register primary + standby services

```bash
curl -X POST http://localhost:8000/api/v1/services \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"billing-api","url":"http://service_a:9001/health","region":"region-a","priority":1,"is_primary":true}'
```

```bash
curl -X POST http://localhost:8000/api/v1/services \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"billing-api","url":"http://service_b:9002/health","region":"region-b","priority":2,"is_primary":false}'
```

### 3. Trigger manual backup

```bash
curl -X POST http://localhost:8000/api/v1/backups/1 \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Simulate regional outage on primary

```bash
curl -X POST "http://localhost:9001/toggle-failure?failing=true"
```

Run system-wide heartbeat check:

```bash
curl -X POST http://localhost:8000/api/v1/services/heartbeat/all \
  -H "Authorization: Bearer $TOKEN"
```

Check failover state:

```bash
curl -X GET http://localhost:8000/api/v1/dr/regions \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Run recovery workflow

```bash
curl -X POST "http://localhost:8000/api/v1/dr/recover/1?reason=Primary%20region%20outage" \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Observe system and metrics

```bash
curl -X GET http://localhost:8000/api/v1/observability/system-status \
  -H "Authorization: Bearer $TOKEN"
```

```bash
curl -X GET http://localhost:8000/api/v1/observability/failovers \
  -H "Authorization: Bearer $TOKEN"
```

```bash
curl -X GET http://localhost:8000/api/v1/observability/metrics/recovery \
  -H "Authorization: Bearer $TOKEN"
```

```bash
curl -X GET http://localhost:8000/metrics
```

## Dashboard Usage

1. Open `http://localhost:5173`
2. Sign in with an API user (`admin` by default)
3. Watch live updates every 5 seconds for:
   - active/standby region state
   - service health by region
   - failover event timeline
   - RTO/RPO aggregate metrics
4. Use **Manual Failover** button to simulate operator-triggered switch

## Security Model

- `admin`:
  - create/register services
  - create users
  - full access to all DR operations
- `operator`:
  - health checks, failover, backups, restore, observability

## Health Endpoints

- `/health` and `/health/live`: liveness
- `/health/ready`: readiness (checks PostgreSQL + Redis, returns `503` when dependencies are unavailable)

## Notes for Production Hardening

- Add refresh tokens and short-lived access tokens
- Replace local object-store simulation with S3 + cross-region replication
- Add message signing and strict JWT key rotation
- Add OpenTelemetry traces and Prometheus scrape configs
- Use K8s HPA and multi-AZ deployment for API and worker services
