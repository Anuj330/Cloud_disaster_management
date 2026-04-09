#!/usr/bin/env bash
set -euo pipefail

# 30-minute DR Game Day Script
# Usage:
#   chmod +x dr_game_day.sh
#   ./dr_game_day.sh
#
# Optional env overrides:
#   BASE_URL=http://localhost:8000
#   PRIMARY_MOCK=http://localhost:9001
#   PRIMARY_REGION=region-a
#   STANDBY_REGION=region-b
#   ADMIN_USER=admin
#   ADMIN_PASS=<set-required-password>
#   SERVICE_NAME=billing-api

BASE_URL="${BASE_URL:-http://localhost:8000}"
PRIMARY_MOCK="${PRIMARY_MOCK:-http://localhost:9001}"
PRIMARY_REGION="${PRIMARY_REGION:-region-a}"
STANDBY_REGION="${STANDBY_REGION:-region-b}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-}"
SERVICE_NAME="${SERVICE_NAME:-billing-api}"

START_EPOCH="$(date +%s)"
TS() { date +"%Y-%m-%d %H:%M:%S"; }
ELAPSED() { echo "$(( $(date +%s) - START_EPOCH ))"; }
LOG() { echo "[$(TS)] [T+$(ELAPSED)s] $*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1"; exit 1; }
}
need_cmd curl
need_cmd jq
need_cmd docker

if [[ -z "${ADMIN_PASS}" ]]; then
  echo "ADMIN_PASS is required. Export ADMIN_PASS before running this script."
  exit 1
fi

api_post_json() {
  local path="$1"
  local body="$2"
  curl -sS -X POST "${BASE_URL}${path}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "${body}"
}

api_post_form() {
  local path="$1"
  local form="$2"
  curl -sS -X POST "${BASE_URL}${path}" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "${form}"
}

api_post() {
  local path="$1"
  curl -sS -X POST "${BASE_URL}${path}" \
    -H "Authorization: Bearer ${TOKEN}"
}

api_get() {
  local path="$1"
  curl -sS -X GET "${BASE_URL}${path}" \
    -H "Authorization: Bearer ${TOKEN}"
}

assert_http_200() {
  local code="$1"
  local step="$2"
  [[ "$code" == "200" ]] || { echo "FAIL ${step} (HTTP ${code})"; exit 1; }
}

LOG "=== Phase 0 (T+0 to T+2m): Bring up platform ==="
docker compose up -d --build

LOG "Waiting for API health..."
for _ in {1..60}; do
  code="$(curl -s -o /tmp/dr_health.json -w '%{http_code}' "${BASE_URL}/health" || true)"
  if [[ "${code}" == "200" ]]; then
    LOG "API is healthy"
    break
  fi
  sleep 2
done
code="$(curl -s -o /tmp/dr_health.json -w '%{http_code}' "${BASE_URL}/health" || true)"
assert_http_200 "$code" "API health check"

LOG "=== Phase 1 (T+2 to T+5m): Authenticate + baseline ==="
LOGIN_JSON="$(api_post_form "/api/v1/auth/token" "username=${ADMIN_USER}&password=${ADMIN_PASS}")"
TOKEN="$(echo "${LOGIN_JSON}" | jq -r '.access_token // empty')"
[[ -n "${TOKEN}" ]] || { echo "Could not fetch token. Response: ${LOGIN_JSON}"; exit 1; }
LOG "Token acquired"

LOG "Register primary service (${PRIMARY_REGION})"
SVC1="$(api_post_json "/api/v1/services" "{\"name\":\"${SERVICE_NAME}\",\"url\":\"http://service_a:9001/health\",\"region\":\"${PRIMARY_REGION}\",\"priority\":1,\"is_primary\":true}")"
echo "${SVC1}" | jq .
PRIMARY_ID="$(echo "${SVC1}" | jq -r '.id // empty')"

LOG "Register standby service (${STANDBY_REGION})"
SVC2="$(api_post_json "/api/v1/services" "{\"name\":\"${SERVICE_NAME}\",\"url\":\"http://service_b:9002/health\",\"region\":\"${STANDBY_REGION}\",\"priority\":2,\"is_primary\":false}")"
echo "${SVC2}" | jq .

if [[ -z "${PRIMARY_ID}" ]]; then
  LOG "Service may already exist. Resolving primary service id from list..."
  PRIMARY_ID="$(api_get "/api/v1/services" | jq -r ".[] | select(.name==\"${SERVICE_NAME}\" and .region==\"${PRIMARY_REGION}\") | .id" | head -n1)"
fi
[[ -n "${PRIMARY_ID}" ]] || { echo "Could not resolve primary service id"; exit 1; }

LOG "Create baseline backup for service_id=${PRIMARY_ID}"
api_post "/api/v1/backups/${PRIMARY_ID}" | jq .

LOG "Check initial region state"
REGIONS_BEFORE="$(api_get "/api/v1/dr/regions")"
echo "${REGIONS_BEFORE}" | jq .

LOG "=== Phase 2 (T+5 to T+10m): Failure injection ==="
LOG "Inject failure on primary mock service (${PRIMARY_MOCK})"
curl -sS -X POST "${PRIMARY_MOCK}/toggle-failure?failing=true" | jq .

LOG "Trigger immediate health scan"
SCAN="$(api_post "/api/v1/services/heartbeat/all")"
echo "${SCAN}" | jq .

LOG "=== Phase 3 (T+10 to T+15m): Failover validation ==="
REGIONS_AFTER="$(api_get "/api/v1/dr/regions")"
echo "${REGIONS_AFTER}" | jq .

ACTIVE_REGION="$(echo "${REGIONS_AFTER}" | jq -r '.active_region')"
if [[ "${ACTIVE_REGION}" == "${STANDBY_REGION}" ]]; then
  LOG "Failover validated: active region switched to ${ACTIVE_REGION}"
else
  LOG "Active region is ${ACTIVE_REGION}. Checking failover logs for context..."
fi

LOG "Failover events:"
FAILOVERS="$(api_get "/api/v1/observability/failovers")"
echo "${FAILOVERS}" | jq '.[0:5]'

LOG "=== Phase 4 (T+15 to T+22m): Recovery workflow ==="
RECOVERY_RESP="$(api_post "/api/v1/dr/recover/${PRIMARY_ID}?reason=Primary%20region%20outage%20game%20day")"
echo "${RECOVERY_RESP}" | jq .
TASK_ID="$(echo "${RECOVERY_RESP}" | jq -r '.task_id // empty')"
LOG "Recovery task queued: ${TASK_ID:-N/A}"

LOG "Waiting 10 seconds for async workflow completion..."
sleep 10

LOG "Recovery workflow list:"
WORKFLOWS="$(api_get "/api/v1/observability/workflows")"
echo "${WORKFLOWS}" | jq '.[0:5]'

WF_ID="$(echo "${WORKFLOWS}" | jq -r '.[] | select(.service_id=='"${PRIMARY_ID}"') | .id' | head -n1)"
if [[ -n "${WF_ID}" ]]; then
  LOG "Workflow logs for workflow_id=${WF_ID}:"
  api_get "/api/v1/observability/workflows/${WF_ID}/logs" | jq .
else
  LOG "No workflow found yet for service_id=${PRIMARY_ID}"
fi

LOG "=== Phase 5 (T+22 to T+27m): RTO/RPO + observability checks ==="
METRICS="$(api_get "/api/v1/observability/metrics/recovery")"
echo "${METRICS}" | jq .

RTO="$(echo "${METRICS}" | jq -r '.avg_rto_seconds // "null"')"
RPO="$(echo "${METRICS}" | jq -r '.avg_rpo_seconds // "null"')"
LOG "Computed averages => RTO=${RTO}s, RPO=${RPO}s"

LOG "System status snapshot:"
api_get "/api/v1/observability/system-status" | jq .

LOG "Prometheus metrics sample:"
curl -sS "${BASE_URL}/metrics" | grep -E "dr_failover_events_total|dr_backups_created_total|dr_recovery_workflows_total|dr_http_requests_total" | head -n 20 || true

LOG "=== Phase 6 (T+27 to T+30m): Cleanup + restore primary ==="
LOG "Restore primary mock service health"
curl -sS -X POST "${PRIMARY_MOCK}/toggle-failure?failing=false" | jq .

LOG "Run heartbeat scan after restore"
api_post "/api/v1/services/heartbeat/all" | jq .

LOG "Final region state:"
api_get "/api/v1/dr/regions" | jq .

LOG "=== Game Day Summary ==="
echo "- Active region now: $(api_get "/api/v1/dr/regions" | jq -r '.active_region')"
echo "- Latest failover reason: $(api_get "/api/v1/observability/failovers" | jq -r '.[0].reason // "none"')"
echo "- Avg RTO seconds: $(api_get "/api/v1/observability/metrics/recovery" | jq -r '.avg_rto_seconds // "null"')"
echo "- Avg RPO seconds: $(api_get "/api/v1/observability/metrics/recovery" | jq -r '.avg_rpo_seconds // "null"')"
echo

echo "DR game day run completed."
