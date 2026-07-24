#!/usr/bin/env bash
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/traxia}"
GATEWAY_DIR="$(cd "$(dirname "$0")/gateway" && pwd)"
FAILURES=0
PASSED=0

run_test() {
  local file="$1"
  local name
  name="$(basename "$file")"
  printf "  %-55s " "$name"

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
echo "=== Loading gateway seed data ==="
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$GATEWAY_DIR/00_gateway_seed.sql" -q
echo "  seed loaded."

echo ""
echo "=== Running gateway auth tests (§8.7.0) ==="
run_test "$GATEWAY_DIR/01_activation.sql"
run_test "$GATEWAY_DIR/02_refresh.sql"
run_test "$GATEWAY_DIR/03_revocation.sql"
run_test "$GATEWAY_DIR/04_invalid_tokens.sql"
run_test "$GATEWAY_DIR/05_activation_reuse.sql"
run_test "$GATEWAY_DIR/06_grace_window.sql"

echo ""
echo "=== Running ingest isolation tests (§8.6) ==="
run_test "$GATEWAY_DIR/07_ingest_isolation.sql"

echo ""
echo "Results: ${PASSED} passed, ${FAILURES} failed"
if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
