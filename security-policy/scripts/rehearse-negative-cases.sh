#!/usr/bin/env bash
# Live rehearsal of the engine's negative-path guarantees through the real CLI
# (the same entry point CI runs), so they can be demonstrated, not just unit
# tested:
#   AC-05 / FR-30 / NFR-03  any missing, malformed or unreachable input must
#                           BLOCK ("fail closed") -- never silently pass.
#   AC-06 / FR-15           identical inputs + identical policy -> identical
#                           decision, output and report, on 3 consecutive runs.
#
# Self-verifying: exits non-zero if ANY expectation is violated, so it can gate
# a CI job directly. Needs only python + PyYAML; no network access, no secrets
# (the "unreachable SonarQube" case points at a closed localhost port).
#
#   usage: security-policy/scripts/rehearse-negative-cases.sh [output-dir]
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1
ENGINE=security-policy/policy_engine.py
POLICY=security-policy/policy.yaml
FIX=security-policy/tests/fixtures
OUT=${1:-security-policy/reports/negative-rehearsal}
rm -rf "$OUT" && mkdir -p "$OUT"

failures=0
fail() { echo "FAIL  $*" >&2; failures=$((failures + 1)); }

# expect_block <name> <expected-error-text> <engine args...>
expect_block() {
  local name=$1 needle=$2; shift 2
  python "$ENGINE" "$@" --report-out "$OUT/$name.md" >"$OUT/$name.out" 2>&1
  local code=$?
  if [[ "$code" -ne 1 ]]; then fail "$name: expected exit 1 (BLOCK), got $code"; return; fi
  if ! grep -q 'SECURITY GATE: BLOCK (fail-closed)' "$OUT/$name.out"; then fail "$name: stdout does not say BLOCK (fail-closed)"; return; fi
  if ! grep -q '\*\*Decision:\*\* BLOCK' "$OUT/$name.md"; then fail "$name: report does not record a BLOCK decision"; return; fi
  if ! grep -q "$needle" "$OUT/$name.md"; then fail "$name: report does not explain the cause (expected '$needle')"; return; fi
  echo "ok    $name -> BLOCK (fail-closed), report explains: $needle"
}

CLEAN=(--gitleaks "$FIX/gitleaks-empty.json" --trivy "$FIX/clean-trivy.json" --sonarqube "$FIX/sonarqube-passed.json" --policy "$POLICY")

echo "== AC-05: fail-closed on bad input (every other input is clean, so the BLOCK is attributable to the one broken thing) =="
expect_block malformed-trivy-report 'JSONDecodeError' \
  --gitleaks "$FIX/gitleaks-empty.json" --trivy "$FIX/malformed-trivy.json" --sonarqube "$FIX/sonarqube-passed.json" --policy "$POLICY"
expect_block missing-gitleaks-report 'FileNotFoundError' \
  --gitleaks "$OUT/does-not-exist.json" --trivy "$FIX/clean-trivy.json" --sonarqube "$FIX/sonarqube-passed.json" --policy "$POLICY"
echo 'not_a_policy: true' >"$OUT/bad-policy.yaml"
expect_block malformed-policy 'malformed' \
  --gitleaks "$FIX/gitleaks-empty.json" --trivy "$FIX/clean-trivy.json" --sonarqube "$FIX/sonarqube-passed.json" --policy "$OUT/bad-policy.yaml"
expect_block sonarqube-unreachable 'Failed to fetch SonarQube' \
  --gitleaks "$FIX/gitleaks-empty.json" --trivy "$FIX/clean-trivy.json" --sonarqube "$OUT/never-fetched.json" \
  --sonar-project-key rehearsal --sonar-organization rehearsal --sonar-token not-a-real-token \
  --sonar-host-url http://127.0.0.1:9 --policy "$POLICY"

# determinism <name> <expected-exit> <engine args...>
determinism() {
  local name=$1 want=$2; shift 2
  local i code
  for i in 1 2 3; do
    python "$ENGINE" "$@" --report-out "$OUT/$name.$i.md" >"$OUT/$name.$i.out" 2>&1
    code=$?
    if [[ "$code" -ne "$want" ]]; then fail "$name run $i: expected exit $want, got $code"; return; fi
    # "Generated" is the only intentionally time-varying line in the report.
    grep -v '^\*\*Generated:\*\*' "$OUT/$name.$i.md" >"$OUT/$name.$i.norm"
  done
  for i in 2 3; do
    cmp -s "$OUT/$name.1.out" "$OUT/$name.$i.out" || { fail "$name: stdout of run $i differs from run 1"; return; }
    cmp -s "$OUT/$name.1.norm" "$OUT/$name.$i.norm" || { fail "$name: report of run $i differs from run 1"; return; }
  done
  echo "ok    $name -> 3 identical runs, decision: $(head -n1 "$OUT/$name.1.out")"
}

echo "== AC-06: deterministic re-evaluation (3 runs each) =="
determinism deterministic-pass 0 "${CLEAN[@]}"
determinism deterministic-block 1 \
  --gitleaks "$FIX/gitleaks-sample.json" --trivy "$FIX/trivy-sample.json" --sonarqube "$FIX/sonarqube-failed.json" --policy "$POLICY"

echo
if [[ "$failures" -ne 0 ]]; then
  echo "NEGATIVE-CASE REHEARSAL FAILED: $failures expectation(s) violated (evidence in $OUT)" >&2
  exit 1
fi
echo "NEGATIVE-CASE REHEARSAL PASSED: 4 fail-closed cases + 2 determinism cases (evidence in $OUT)"
