#!/usr/bin/env bash
set -euo pipefail

# Full stack smoke + edge-case test runner.
# Usage:
#   chmod +x scripts/smoke_test.sh
#   ./scripts/smoke_test.sh
#
# Optional env overrides:
#   BASE_URL=http://localhost:8000
#   TEST_ADMIN_USER=smokeadmin
#   TEST_ADMIN_PASS=SmokeAdmin#2026!
#   SKIP_REDIS_EDGE=false

BASE_URL="${BASE_URL:-http://localhost:8000}"
TEST_ADMIN_USER="${TEST_ADMIN_USER:-smokeadmin}"
TEST_ADMIN_PASS="${TEST_ADMIN_PASS:-SmokeAdmin#2026!}"
SKIP_REDIS_EDGE="${SKIP_REDIS_EDGE:-false}"

REDIS_STOPPED=0
PASS_COUNT=0

ts() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; PASS_COUNT=$((PASS_COUNT + 1)); }

cleanup() {
  if [[ "${REDIS_STOPPED}" == "1" ]]; then
    docker compose start redis >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

need_cmd docker
need_cmd curl
need_cmd jq

log "Starting stack"
docker compose up -d --build >/tmp/smoke_compose_up.log 2>&1 || {
  cat /tmp/smoke_compose_up.log
  fail "docker compose up failed"
}
pass "stack started"

log "Waiting for API liveness"
for _ in {1..60}; do
  code="$(curl -s -o /tmp/smoke_live.json -w '%{http_code}' "${BASE_URL}/health/live" || true)"
  [[ "${code}" == "200" ]] && break
  sleep 2
done
[[ "${code}" == "200" ]] || fail "liveness check failed"
pass "liveness endpoint healthy"

log "Waiting for API readiness"
for _ in {1..60}; do
  code="$(curl -s -o /tmp/smoke_ready.json -w '%{http_code}' "${BASE_URL}/health/ready" || true)"
  [[ "${code}" == "200" ]] && break
  sleep 2
done
[[ "${code}" == "200" ]] || fail "readiness check failed"
pass "readiness endpoint healthy"

log "Ensuring test admin user exists"
docker compose exec -T \
  -e TEST_ADMIN_USER="${TEST_ADMIN_USER}" \
  -e TEST_ADMIN_PASS="${TEST_ADMIN_PASS}" \
  api python3 -c "
from app.core.database import SessionLocal
from app.models.entities import User
from app.core.security import hash_password
import os
db = SessionLocal()
username = os.environ['TEST_ADMIN_USER']
password = os.environ['TEST_ADMIN_PASS']
u = db.query(User).filter(User.username == username).first()
if not u:
    db.add(User(username=username, password_hash=hash_password(password), role='admin'))
else:
    u.password_hash = hash_password(password)
    u.role = 'admin'
db.commit()
db.close()
" >/tmp/smoke_admin_create.log 2>&1 || {
  cat /tmp/smoke_admin_create.log
  fail "failed to create or update test admin user"
}
pass "test admin user ready"

log "Verifying unauthorized access is blocked"
code="$(curl -s -o /tmp/smoke_unauth.json -w '%{http_code}' "${BASE_URL}/api/v1/services" || true)"
[[ "${code}" == "401" ]] || fail "expected 401 without token, got ${code}"
pass "unauthorized access blocked"

log "Fetching auth token for test admin"
TOKEN="$(curl -s -X POST "${BASE_URL}/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${TEST_ADMIN_USER}&password=${TEST_ADMIN_PASS}" | jq -r '.access_token // empty')"
[[ -n "${TOKEN}" ]] || fail "token fetch failed"
pass "auth token issued"

log "Checking login lockout edge case"
LOCK_USER="locktest_$(date +%s)"
for i in 1 2 3 4 5; do
  code="$(curl -s -o /tmp/smoke_lock_${i}.json -w '%{http_code}' \
    -X POST "${BASE_URL}/api/v1/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${LOCK_USER}&password=wrong-pass")"
  [[ "${code}" == "401" ]] || fail "expected 401 for attempt ${i}, got ${code}"
done
code="$(curl -s -o /tmp/smoke_lock_6.json -w '%{http_code}' \
  -X POST "${BASE_URL}/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${LOCK_USER}&password=wrong-pass")"
[[ "${code}" == "429" ]] || fail "expected 429 on lockout attempt, got ${code}"
pass "auth lockout behavior correct"

SERVICE_NAME="smoke-billing-$(date +%s)"
log "Creating primary and standby test services: ${SERVICE_NAME}"
primary_json="$(curl -s -X POST "${BASE_URL}/api/v1/services" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${SERVICE_NAME}\",\"url\":\"http://service_a:9001/health\",\"region\":\"region-a\",\"priority\":1,\"is_primary\":true}")"
standby_json="$(curl -s -X POST "${BASE_URL}/api/v1/services" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${SERVICE_NAME}\",\"url\":\"http://service_b:9002/health\",\"region\":\"region-b\",\"priority\":2,\"is_primary\":false}")"

PRIMARY_ID="$(echo "${primary_json}" | jq -r '.id // empty')"
[[ -n "${PRIMARY_ID}" ]] || fail "failed to create primary service: ${primary_json}"
standby_id="$(echo "${standby_json}" | jq -r '.id // empty')"
[[ -n "${standby_id}" ]] || fail "failed to create standby service: ${standby_json}"
pass "test services created"

log "Triggering manual backup"
code="$(curl -s -o /tmp/smoke_backup.json -w '%{http_code}' \
  -X POST "${BASE_URL}/api/v1/backups/${PRIMARY_ID}" \
  -H "Authorization: Bearer ${TOKEN}")"
[[ "${code}" == "200" ]] || fail "backup creation failed with code ${code}"
pass "manual backup succeeded"

log "Testing duplicate recovery request handling"
rec1="$(curl -s -X POST "${BASE_URL}/api/v1/dr/recover/${PRIMARY_ID}?reason=smoke-duplicate-1" \
  -H "Authorization: Bearer ${TOKEN}")"
rec2="$(curl -s -X POST "${BASE_URL}/api/v1/dr/recover/${PRIMARY_ID}?reason=smoke-duplicate-2" \
  -H "Authorization: Bearer ${TOKEN}")"
t1="$(echo "${rec1}" | jq -r '.task_id // empty')"
t2="$(echo "${rec2}" | jq -r '.task_id // empty')"
[[ -n "${t1}" && -n "${t2}" ]] || fail "recovery requests did not return task ids"

workflow_count=0
latest_status="none"
for _ in {1..20}; do
  workflows="$(curl -s -H "Authorization: Bearer ${TOKEN}" "${BASE_URL}/api/v1/observability/workflows")"
  workflow_count="$(echo "${workflows}" | jq "[.[] | select(.service_id==${PRIMARY_ID})] | length")"
  latest_status="$(echo "${workflows}" | jq -r "[.[] | select(.service_id==${PRIMARY_ID})][0].status // \"none\"")"
  if [[ "${workflow_count}" -ge 1 && "${latest_status}" == "COMPLETED" ]]; then
    break
  fi
  sleep 1
done
[[ "${workflow_count}" -eq 1 ]] || fail "expected one workflow for duplicate recovery, found ${workflow_count}"
[[ "${latest_status}" == "COMPLETED" ]] || fail "expected completed workflow, got ${latest_status}"
pass "duplicate recovery dedupe works"

if [[ "${SKIP_REDIS_EDGE}" != "true" ]]; then
  log "Testing readiness degradation with Redis stop/start"
  docker compose stop redis >/tmp/smoke_stop_redis.log 2>&1 || {
    cat /tmp/smoke_stop_redis.log
    fail "failed to stop redis for readiness edge test"
  }
  REDIS_STOPPED=1
  sleep 2

  live_code="$(curl -s -o /tmp/smoke_live_redis_stop.json -w '%{http_code}' "${BASE_URL}/health/live" || true)"
  ready_code="$(curl -s -o /tmp/smoke_ready_redis_stop.json -w '%{http_code}' "${BASE_URL}/health/ready" || true)"
  [[ "${live_code}" == "200" ]] || fail "expected live 200 when redis down, got ${live_code}"
  [[ "${ready_code}" == "503" ]] || fail "expected ready 503 when redis down, got ${ready_code}"

  docker compose start redis >/tmp/smoke_start_redis.log 2>&1 || {
    cat /tmp/smoke_start_redis.log
    fail "failed to restart redis after readiness edge test"
  }
  REDIS_STOPPED=0
  sleep 2
  ready_code="$(curl -s -o /tmp/smoke_ready_redis_restart.json -w '%{http_code}' "${BASE_URL}/health/ready" || true)"
  [[ "${ready_code}" == "200" ]] || fail "expected ready 200 after redis restart, got ${ready_code}"
  pass "readiness degradation behavior correct"
fi

log "Smoke suite completed successfully (${PASS_COUNT} checks passed)"
