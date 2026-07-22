#!/usr/bin/env bash
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/traxia}"
TESTS_DIR="$(cd "$(dirname "$0")/isolation" && pwd)"
FAILURES=0
PASSED=0

run_test() {
  local file="$1"
  local name
  name="$(basename "$file")"
  printf "  %-55s " "$name"

  local out
  # -v ON_ERROR_STOP=1 makes psql exit non-zero on SQL errors, which we capture
  # in the exit-code check below alongside the "not ok" TAP grep.
  out="$(psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$file" -A -t -q 2>&1)"
  local psql_exit=$?

  if [ $psql_exit -ne 0 ] || echo "$out" | grep -q '^not ok'; then
    echo "FAIL"
    echo "$out" | grep '^not ok' | sed 's/^/    /'
    FAILURES=$((FAILURES + 1))
  else
    echo "OK"
    PASSED=$((PASSED + 1))
  fi
}

echo ""
echo "=== Ensuring pgTAP extension is available ==="
psql "$DB_URL" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS pgtap;" -q
echo "  pgtap ready."

echo ""
echo "=== Loading seed data ==="
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$TESTS_DIR/00_seed.sql" -q
echo "  seed loaded."

echo ""
echo "=== Running isolation tests (Section 8.4) ==="
run_test "$TESTS_DIR/01_tenant_isolation.sql"
run_test "$TESTS_DIR/02_site_scoped_isolation.sql"
run_test "$TESTS_DIR/03_partner_isolation.sql"
run_test "$TESTS_DIR/04_tenant_keeps_visibility_of_ceded_zones.sql"

echo ""
echo "Results: ${PASSED} passed, ${FAILURES} failed"
if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
