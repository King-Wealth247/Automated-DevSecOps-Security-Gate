# Acceptance Criteria — Evidence

Task 4.7. A consolidated record of the evidence behind each of the SRS's 8 acceptance
criteria (AC-01–AC-08), pulled together from GitHub Actions run logs, commit history, and
this project's own testing — cross-referenced against `IMPLEMENTATION_PLAN.md` §6 and
§23, not restated from memory. Compiled 2026-09-29, against the pipeline's first fully
fully-green end-to-end state (run `36593239493`).

**Status key:** `[x]` demonstrated live, end to end · `[~]` demonstrated in substance,
with a caveat noted · `[?]` not yet demonstrated.

For the system this evidence is about, see
[`docs/architecture/ARCHITECTURE.md`](./architecture/ARCHITECTURE.md) and
[`docs/diagrams/`](./diagrams/README.md).

---

## AC-01 — Clean build → PASS → auto-deploy — `[~]`

**Claim:** a build with no policy-violating findings results in a PASS decision and an
automatic deployment.

Juice Shop is deliberately, organically vulnerable, so a live scan of the real
application can never PASS under this project's thresholds (`policy.yaml`) without
weakening them — which is off-limits (task 2.5). PASS is instead demonstrated by running
the identical engine and policy against controlled clean fixtures
(`security-policy/tests/fixtures/gitleaks-empty.json`, `clean-trivy.json`,
`sonarqube-passed.json`), reachable only via `workflow_dispatch`'s `use_clean_fixtures`
input, never push/PR.

- **PASS decision, confirmed live 2026-09-05:** `policy-gate-pass-rehearsal` job —
  `SECURITY GATE: PASS`, all 5 thresholds `[OK]`, report artifact uploaded. In the same
  run, the real `policy-gate` job independently still BLOCKed Juice Shop's actual code —
  proving both PASS and BLOCK come out of the identical engine, not two different code
  paths.
- **Auto-deploy, confirmed live 2026-09-28/29:** runs `36407858635` and `36593239493`
  (both `workflow_dispatch`, `use_clean_fixtures: true`) carried that PASS decision
  through:
  - `publish` — downloaded `docker-build`'s artifact, verified the image ID matched
    exactly, pushed to GHCR (`digest: sha256:f1df1778...`).
  - `deploy-flyio-temp` — deployed that exact published image to Fly.io:
    `https://devsecops-juice-shop-temp.fly.dev/`.

**Why `[~]` and not `[x]`:** the deploy target is Fly.io, a documented *temporary*
stand-in while AWS OIDC federation (the real, final target per the SRS) remains blocked
on an AWS Support case (task 4.3). The mechanism — PASS decision → verified image →
deploy — is fully proven; only the specific target isn't AWS EC2 yet.

---

## AC-02 — Planted fake secret → Gitleaks finds it → BLOCK, ×3 — `[~]`

**Claim:** a deliberately planted secret in Juice Shop is detected by Gitleaks and
results in an enforced BLOCK, repeatably.

- **First attempt failed — caught by live validation, not assumed to work:** the
  original planted value
  (`fake_api_key = "sk_test_AC02FAKE1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ"`, commit
  `722df6af2`) produced **no new finding** in CI run `33162701543` — Gitleaks' own
  false-positive filtering rejected the "FAKE"/sequential-looking token.
- **Fixed and confirmed live:** replaced with
  `generic_api_key = "8f1c4a9d3e7b6c2081af59d34e7b0261c9f4a83d7e6b0125c"` (commit
  `bafa969b3`). The very next run showed the leak count move **69 → 70**, with a new
  `generic-api-key` finding at `juice-shop/DEVSECOPS_AC02_FIXTURE.txt:17`, matched by
  rule, file, line, and commit.
- **Enforcement (not just detection):** since 2026-08-29 the unified Security Policy
  Engine — not `gitleaks-scan` itself, which is deliberately report-only — has
  independently BLOCKed on real Gitleaks findings against Juice Shop's actual code
  multiple times (runs `33904104338`, `34462487406`, and the 2026-09-24 run).

**Why `[~]` and not `[x]`:** detection and enforcement are both proven live, but not as
one dedicated, formally-labeled "×3" rehearsal the way AC-05/AC-06 now have
(`policy-gate-negative-rehearsal`). A candidate follow-up: extend that job, or a sibling
one, to plant-and-detect 3 times through the real CLI.

---

## AC-03 — Outdated base image → Trivy CRITICAL → BLOCK, ×3 — `[~]`

**Claim:** a container image with known CRITICAL vulnerabilities is detected by Trivy and
results in an enforced BLOCK, repeatably.

Juice Shop's own image genuinely and consistently has real CRITICAL findings — no
planting needed (task 2.5's calibration baseline: 8 CRITICAL / 38 HIGH / 36 MEDIUM / 11
LOW). Every push-triggered run against real code has demonstrated Trivy CRITICAL → BLOCK
in substance:

| Run | Date | Result |
|---|---|---|
| `33904104338` | 2026-09-04 | Real Trivy findings → `SECURITY GATE: BLOCK` |
| `34462487406` | 2026-09-11 | Real Trivy findings → BLOCK (no GHCR tag pushed) |
| (2026-09-24 run) | 2026-09-24 | Real Trivy/Gitleaks findings → genuine `SECURITY GATE: BLOCK` (not fail-closed default) |

**Why `[~]` and not `[x]`:** these are 3 independent real observations across different
pushes, not one dedicated, controlled ×3 rehearsal run back-to-back through the real CLI.
The engine-level determinism guarantee (AC-06) already proves that identical BLOCK-input
re-evaluates identically 3× — what's missing is a Trivy-CRITICAL-specific case added to
`policy-gate-negative-rehearsal` (or a sibling job) for a single, self-contained,
on-demand demonstration.

---

## AC-04 — Acceptable low-severity-only build → PASS → deploy — `[~]`

**Claim:** a build with only medium/low-severity findings (within policy) still PASSes
and deploys.

Identical evidence and identical caveat as AC-01 — `policy.yaml` sets
`medium_vulnerabilities`/`low_vulnerabilities` to `allowed: null` (unlimited,
report-only) specifically so this scenario is reachable without weakening the
secrets/critical/high thresholds. The same clean-fixture PASS demonstration and the same
live `publish` → `deploy-flyio-temp` chain (runs `36407858635`, `36593239493`) cover
this criterion.

**Why `[~]` and not `[x]`:** same reason as AC-01 — Fly.io, not AWS EC2, is the current
deploy target.

---

## AC-05 — Simulated scanner failure → BLOCK by default — `[x]`

**Claim:** if a scanner's output is missing, malformed, or unreachable, the gate fails
closed (BLOCKs) rather than failing open or crashing.

- **Unit-tested** (27 tests, `security-policy/tests/test_policy_engine.py`): a
  missing/malformed policy, a missing/malformed scanner report, a SonarQube **timeout**,
  and a SonarQube **HTTP 401** (mirroring the real 2026-09-25 revoked-`SONAR_TOKEN`
  incident).
- **Real live BLOCK observed, 2026-09-24:** `SECURITY GATE: BLOCK (fail-closed)` when
  `trivy-scan` was skipped and its artifact was genuinely missing — the engine
  documented the BLOCK instead of crashing.
- **Dedicated live rehearsal, confirmed 2026-09-27 (run `36343387712`):** the
  `policy-gate-negative-rehearsal` job ran 4 cases through the real CLI and all 4 BLOCKed
  as required:

  ```
  ok    malformed-trivy-report    -> BLOCK (fail-closed)
  ok    missing-gitleaks-report   -> BLOCK (fail-closed)
  ok    malformed-policy          -> BLOCK (fail-closed)
  ok    sonarqube-unreachable     -> BLOCK (fail-closed)
  ```

  Also mutation-tested locally: swapping a bad-input case for a clean one makes the
  rehearsal script itself fail, confirming it can actually detect a real regression.

---

## AC-06 — Deterministic re-evaluation — `[x]`

**Claim:** identical inputs and policy always produce identical outputs.

- **Unit-tested** at both the evaluator level (3× re-evaluation, since 2026-08-29) and
  the engine level (3 full `main()` runs — identical exit code, stdout, and report
  modulo the intentionally time-varying `Generated:` line).
- **Dedicated live rehearsal, confirmed 2026-09-27 (run `36343387712`):**
  `policy-gate-negative-rehearsal` repeated both a PASS and a BLOCK input 3× each through
  the real CLI, byte-comparing stdout and normalized reports:

  ```
  ok    deterministic-pass  -> 3 identical runs, decision: SECURITY GATE: PASS
  ok    deterministic-block -> 3 identical runs, decision: SECURITY GATE: BLOCK
  ```

---

## AC-07 — Report generated every run — `[x]`

**Claim:** every pipeline run produces a human-readable security report.

`policy-gate`'s `Upload security report` step (`if: always()`, and
`if-no-files-found: error` — a missing report hard-fails the job, it can't silently not
happen) has uploaded the `security-report` Markdown artifact in every live run inspected
this session, PASS and BLOCK alike, going back to run `33904104338` (2026-09-04).

---

## AC-08 — Slack notification every run — `[x]`

**Claim:** every pipeline run posts a notification to Slack.

`Notify Slack` runs on `if: always() && (env.SLACK_WEBHOOK_URL != '' ||
inputs.simulate_broken_slack == true)` — fires on every real run now that
`SLACK_WEBHOOK_URL` is permanently configured. Both directions are live-confirmed:

- **Success path:** message delivered to the real Slack channel (confirmed once the
  webhook secret was created).
- **Failure path, confirmed 2026-09-27 (run `36343387712`):** a deliberately invalid
  webhook URL (`simulate_broken_slack: true`) got a real HTTP 404 from Slack; the step
  correctly detected it (not swallowed by `curl`'s own exit code), logged
  `::warning title=Slack notification failed::HTTP 404 from the webhook (no_team). The
  gate decision (PASS) and downstream jobs are unaffected.`, and failed only its own
  step — the gate decision and every downstream job were unaffected.

---

## Summary

| AC | Status | What's fully proven | What's still open |
|---|---|---|---|
| AC-01 | `[~]` | PASS decision live; full auto-deploy chain live (Fly.io) | Real target is AWS EC2, not Fly.io |
| AC-02 | `[~]` | Detection live, repeatable; enforcement live (multiple runs) | No single dedicated ×3 rehearsal |
| AC-03 | `[~]` | Real BLOCK observed live, 3 independent runs | No single dedicated ×3 rehearsal |
| AC-04 | `[~]` | Same as AC-01 | Same as AC-01 |
| AC-05 | `[x]` | Unit-tested + dedicated live rehearsal, all 4 cases | — |
| AC-06 | `[x]` | Unit-tested + dedicated live rehearsal, both cases | — |
| AC-07 | `[x]` | Every run, hard-fails if missing | — |
| AC-08 | `[x]` | Both success and failure paths live | — |

4 of 8 fully closed; the remaining 4 are all demonstrated in substance with real,
repeated live evidence — none are untested guesses — and share exactly two open threads:
formalizing AC-02/AC-03 as dedicated ×3 rehearsals (mirroring AC-05/AC-06's pattern), and
replacing Fly.io with the real AWS EC2 target once task 4.3's OIDC federation is
unblocked.
