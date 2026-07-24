#!/usr/bin/env bash
# Run all Fase 2 backoffice tests — pgTAP RLS tests + Python HTTP tests.
# Usage: ./tests/run_backoffice_tests.sh [DATABASE_URL]
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://rodrigogalindo@localhost:5432/traxia}"
BACKOFFICE_DIR="$(cd "$(dirname "$0")/backoffice" && pwd)"
FAILURES=0
PASSED=0

run_pgtap() {
  local file="$1"
  local name
  name="$(basename "$file")"
  printf "  %-60s " "$name"

  local out
  out="$(psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$file" -A -t -q 2>&1)"
  local psql_exit=$?

  if [ $psql_exit -ne 0 ] || echo "$out" | grep -q '^not ok'; then
    echo "FAIL"
    echo "$out" | grep '^not ok' | sed 's/^/    /'
    if [ $psql_exit -ne 0 ]; then
      echo "$out" | tail -5 | sed 's/^/    ERROR: /'
    fi
    FAILURES=$((FAILURES + 1))
  else
    echo "OK"
    PASSED=$((PASSED + 1))
  fi
}

echo ""
echo "=== Loading backoffice seed data ==="
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$BACKOFFICE_DIR/00_backoffice_seed.sql" -q
echo "  seed loaded."

echo ""
echo "=== Running backoffice RLS tests (pgTAP) ==="
run_pgtap "$BACKOFFICE_DIR/01_rls_backoffice.sql"

echo ""
echo "=== Running backoffice HTTP tests (pytest) ==="
if DATABASE_URL="$DB_URL" JWT_SECRET="${JWT_SECRET:-dev-secret-change-me}" \
   python3 -m pytest tests/backoffice/test_backoffice_api.py -v --tb=short 2>&1; then
  echo "  pytest PASSED"
  PASSED=$((PASSED + 1))
else
  echo "  pytest FAILED"
  FAILURES=$((FAILURES + 1))
fi

echo ""
echo "Results: ${PASSED} passed, ${FAILURES} failed"
if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
