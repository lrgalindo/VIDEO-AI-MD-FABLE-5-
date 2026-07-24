#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# Traxia Analytics — Full E2E Smoke Test  (Fases 1-3 integrated)
#
# Single reproducible command — runs from a clean slate.
#
# Usage:
#   ./tests/run_e2e.sh                    # uses ANTHROPIC_API_KEY from env
#   ANTHROPIC_API_KEY=sk-... ./tests/run_e2e.sh
#
# Validates (in sequence):
#   (a) Postgres + RLS + pg_partman partitions
#   (b) Cloud API healthcheck 200
#   (c) Edge Gateway: activates, real YOLO inference, ByteTrack continuity
#   (d) Motor de Acciones: threshold rule fires → action_log entry
#   (e) Copiloto: real Anthropic answer with tenant-scoped data
#   (f) Hallazgos: agent_findings + presigned snapshot URL accessible
#   (g) 60s network outage — zero data loss via SQLite queue
#   +   Frontend: dashboard nginx serves SPA HTML + proxies /v1/ to cloud-api
#
# Requirements:
#   - Docker + docker-compose
#   - python3 with psycopg2-binary + requests  (pip install psycopg2-binary requests)
#   - Run from the repo root
# ────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE="docker-compose -f $REPO_ROOT/docker-compose.e2e.yml"

RED="\033[31m"; GREEN="\033[32m"; YELLOW="\033[33m"; CYAN="\033[36m"; RESET="\033[0m"
info()    { echo -e "${CYAN}[E2E]${RESET}  $*"; }
ok()      { echo -e "${GREEN}[E2E]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[E2E]${RESET}  $*"; }
fail()    { echo -e "${RED}[E2E]${RESET}  $*" >&2; }

echo
echo "════════════════════════════════════════════════════════════════════"
echo "  Traxia Analytics — E2E Smoke Test (Fases 1-3 integradas)"
echo "════════════════════════════════════════════════════════════════════"
echo

# ── Anthropic key warning ──────────────────────────────────────────────────
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  warn "ANTHROPIC_API_KEY not set — items (e) Copiloto and (f) Hallazgos audit"
  warn "will be SKIPPED.  Pass the key to validate the full suite."
  echo
fi

# ── 0. Clean slate ────────────────────────────────────────────────────────────
info "[0/4] Tearing down any previous E2E environment …"
$COMPOSE down --volumes --remove-orphans 2>/dev/null || true
echo

# ── 1. Build + bring up all services ─────────────────────────────────────────
info "[1/4] Building images and starting all services …"
$COMPOSE build --parallel

# Bring up infrastructure tier first, then wait for healthchecks
$COMPOSE up -d postgres minio
info "      Waiting for postgres + minio healthchecks (up to 90s) …"
MAX_INFRA=90; ELAPSED=0
until $COMPOSE ps --format json 2>/dev/null | python3 -c "
import sys,json
services={s['Service']:s.get('Health','') for line in sys.stdin for s in [json.loads(line)] if s.get('Service') in ('postgres','minio')}
ok = all(v=='healthy' for v in services.values()) and len(services)==2
sys.exit(0 if ok else 1)
" 2>/dev/null; do
  if [ "$ELAPSED" -ge "$MAX_INFRA" ]; then
    fail "postgres or minio did not become healthy within ${MAX_INFRA}s"
    $COMPOSE logs --tail=20 postgres minio
    exit 1
  fi
  sleep 5; ELAPSED=$((ELAPSED + 5))
done
ok "      postgres + minio healthy"

# Bring up dependent services — docker-compose respects depends_on ordering
$COMPOSE up -d minio-init migrate
info "      Waiting for migration to complete (up to 60s) …"
sleep 60   # migration runs alembic then exits; seed follows it

$COMPOSE up -d seed-e2e
sleep 10   # seed runs psql then exits

# All application services
$COMPOSE up -d cloud-api httpbin mediamtx ffmpeg-publisher edge-gateway dashboard
echo

# ── 2. Wait for cloud-api ─────────────────────────────────────────────────────
info "[2/4] Waiting for cloud-api to be healthy on localhost:8000 …"
MAX_WAIT=120; ELAPSED=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
  if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
    fail "cloud-api did not respond within ${MAX_WAIT}s"
    $COMPOSE logs --tail=40 cloud-api
    exit 1
  fi
  sleep 5; ELAPSED=$((ELAPSED + 5))
done
ok "cloud-api is healthy"

# Extra warm-up time for edge gateway to activate + YOLO to warm up
info "      Giving edge gateway 60s to activate and start capturing …"
sleep 60
echo

# ── 3. Run smoke test ─────────────────────────────────────────────────────────
info "[3/4] Running smoke_test.py …"
echo

cd "$REPO_ROOT"
DATABASE_URL="postgresql://postgres:postgres@localhost:5433/traxia" \
  CLOUD_API_URL="http://localhost:8000" \
  DASHBOARD_URL="http://localhost:3000" \
  JWT_SECRET="e2e-smoke-test-secret-2026" \
  GATEWAY_ID="e2e-gateway-001" \
  CAMERA_ID="d4e2e000-0000-0000-0000-000000000001" \
  ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  python3 tests/e2e/smoke_test.py
SMOKE_EXIT=$?

echo

# ── 4. Outcome ────────────────────────────────────────────────────────────────
if [ "$SMOKE_EXIT" -eq 0 ]; then
  echo
  echo -e "${GREEN}════════════════════════════════════════════════════════════════════${RESET}"
  echo -e "${GREEN}  [PASS]  Full E2E smoke test — Fases 1-3 validated${RESET}"
  echo -e "${GREEN}════════════════════════════════════════════════════════════════════${RESET}"
  echo
else
  echo
  echo -e "${RED}════════════════════════════════════════════════════════════════════${RESET}"
  echo -e "${RED}  [FAIL]  Smoke test failed — collecting diagnostics …${RESET}"
  echo -e "${RED}════════════════════════════════════════════════════════════════════${RESET}"
  echo
  info "[4/4] Last 50 log lines from each service:"
  for svc in postgres cloud-api edge-gateway minio httpbin; do
    echo
    warn "  ── $svc ──"
    $COMPOSE logs --tail=50 "$svc" 2>/dev/null || true
  done
  exit 1
fi
