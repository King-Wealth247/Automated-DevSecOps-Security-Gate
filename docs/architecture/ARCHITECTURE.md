# Architecture

This is the detailed companion to the README's one-paragraph overview. For diagrams,
see [`docs/diagrams/`](../diagrams/README.md). For current build status against every
requirement, see [`IMPLEMENTATION_PLAN.md`](../../IMPLEMENTATION_PLAN.md).

## Design principle

This project does not build new scanners. It **enforces** the combined output of three
existing ones as a single, automatic, unavoidable deployment gate — replacing the manual
"read three differently-formatted reports and decide" step with a deterministic,
version-controlled policy. [OWASP Juice Shop](https://owasp-juice.shop/) is vendored
unmodified as the realistic test subject; it is not the deliverable.

## Components

### 1. Security scanners (parallel, per run)

| Scanner | Checks | Output |
|---|---|---|
| **Gitleaks** | Secrets/credentials in the repo, including Juice Shop's own source | `gitleaks-report.json` artifact |
| **Trivy** | Known CVEs in the built container image and its dependencies | `trivy-report.json` artifact, scans the *exact* image `docker-build` produced (see below) |
| **SonarQube Cloud** | Security-focused static analysis + its own Quality Gate | Queried live by `policy_engine.py` via SonarCloud's API |

Each scanner job is individually non-blocking (`continue-on-error` on its own
report-only evaluation step, where one exists) — **blocking is unified in exactly one
place**, the Security Policy Engine. This is deliberate: three separately-blocking
scanners would mean three different places a release could be stopped for three
different reasons, which is the exact "manual, ad-hoc decision" problem this project
exists to remove.

### 2. Security Policy Engine (`security-policy/`) — the core contribution

```
security-policy/
├── policy.yaml              version-controlled thresholds (see below)
├── policy_engine.py          CLI entry point / orchestration
├── schema.py                  the normalized Finding schema every parser maps to
├── parsers/
│   ├── gitleaks.py              Gitleaks JSON → Finding[]
│   ├── trivy.py                  Trivy JSON → Finding[]
│   └── sonarqube.py               live SonarCloud API fetch → Finding[]
├── evaluators/
│   └── policy_evaluator.py    Finding[] + policy.yaml → PASS/BLOCK decision
├── report.py                  renders the human-readable security-report.md
├── scripts/
│   └── rehearse-negative-cases.sh   live fail-closed/determinism rehearsal (AC-05/06)
└── tests/                     27 unit tests (pytest)
```

`policy.yaml` (SRS §5.1 schema): each severity category has an `allowed` threshold — a
number blocks when the found count exceeds it, `null` means unlimited (report-only), and
a severity with **no entry at all** defaults to zero-tolerance (fail-closed for unmapped
categories, not fail-open). Currently:

| Category | Allowed |
|---|---|
| `secrets` | 0 |
| `critical_vulnerabilities` | 0 |
| `high_vulnerabilities` | 0 |
| `medium_vulnerabilities` | unlimited |
| `low_vulnerabilities` | unlimited |

Calibrated against Juice Shop's real CI-validated baseline (69 Gitleaks leaks, 8
CRITICAL/38 HIGH/36 MEDIUM/11 LOW Trivy findings) — strict enough on
secrets/critical/high to demonstrably BLOCK, unlimited on medium/low so the gate isn't
permanently unpassable on metrics this project isn't demonstrating BLOCK on.

**Fail-closed, not just fail-safe:** any exception anywhere in the fetch/parse/evaluate
chain — a missing report file, malformed JSON, an unparseable policy, a SonarQube
timeout or HTTP error — is caught and converted to a documented BLOCK, never a bare
crash with no decision recorded. See
[`docs/diagrams/decision-flow.md`](../diagrams/decision-flow.md) for the full data flow
and how this is tested (27 unit tests, plus a live `workflow_dispatch` rehearsal on every
manual run).

### 3. CI/CD orchestration (`.github/workflows/ci.yml`)

One workflow, ten jobs (two of them `workflow_dispatch`-only rehearsals). Full job graph
and rationale: [`docs/diagrams/pipeline-dag.md`](../diagrams/pipeline-dag.md).

The key architectural decision here is **build once, scan that, publish that** —
`docker-build` builds the Juice Shop image exactly once, saves it as an artifact with its
image ID as a job output, and both `trivy-scan` and `publish` load that same artifact and
**re-verify the image ID matches** before doing anything with it. This matters because
Juice Shop deliberately floats its dependencies (no committed lockfile, `node:24` base
tag) — three independent rebuilds at three different moments could genuinely produce
three different images, silently undermining the "the image we shipped is the image we
scanned" guarantee that's the whole point of the gate.

### 4. Publish & deploy

- **GHCR** (`publish` job): on a genuine PASS, pushes the exact scanned image to GitHub
  Container Registry, tagged with the commit SHA.
- **Fly.io** (`deploy-flyio-temp` job): a **temporary** stand-in deploy target while AWS
  OIDC federation is blocked (see below) — deploys the exact published image, no
  rebuild. See [`infra/flyio/README.md`](../../infra/flyio/README.md).
- **AWS EC2** (planned, task 4.3–4.5): the actual final deployment target per the SRS.
  CloudFormation template, IAM role, and an OIDC federation probe are written and
  provisioned (`infra/aws/`), but live authentication is currently blocked on an AWS
  Support case (suspected new-account security hold, not a configuration defect — see
  `IMPLEMENTATION_PLAN.md` task 4.3 for the full root-cause investigation). No long-lived
  AWS credentials are used anywhere — federation only.

### 5. Reporting & notifications

- Every run uploads a Markdown security report (`security-report` artifact,
  `report.py`), PASS or BLOCK alike.
- Every run posts to Slack — success and failure of the *notification itself* are both
  handled: a broken/unreachable webhook is detected (checked by HTTP status, not just
  `curl`'s own exit code), logged with a warning annotation, and fails only its own step
  — the gate decision is never affected by whether Slack is reachable.

### 6. Governance

`.github/CODEOWNERS` requires review on `security-policy/policy.yaml` changes — the one
file that can change what the gate blocks. Paired with branch protection on `main`
(GitHub Settings, not version-controlled) requiring that review before merge, so a
threshold change is never a silent, unreviewed edit.

## What "done" looks like for a run

1. `build-and-test` → `docker-build` → `trivy-scan` (scans the exact built image) all run
   alongside `gitleaks-scan` and `sonarqube-scan`.
2. `policy-gate` runs regardless of any individual scanner's own success/failure
   (`if: always()`) — `policy_engine.py`'s own fail-closed logic is what actually decides
   BLOCK on a missing/malformed input, not a crashed CI job.
3. On PASS: `publish` re-verifies and pushes the exact scanned image to GHCR;
   `deploy-flyio-temp` deploys that exact published image.
4. On BLOCK: both are skipped automatically — no image leaves GHCR, nothing deploys.
5. Either way: a report artifact is uploaded and Slack is notified.

Confirmed end to end, live, for the first time as a single fully-green run on
2026-09-29 (run `36593239493`) — every one of the ten jobs succeeded in the same run.
