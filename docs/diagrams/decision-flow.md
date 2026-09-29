# Security Decision Data Flow

How three differently-formatted scanner reports become one deterministic PASS/BLOCK
decision. This is the core of the project — see
[`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) for the
component-level explanation, and `security-policy/policy_engine.py` for the code.

```mermaid
flowchart LR
    subgraph scanners ["Scanners (parallel jobs)"]
        gl["Gitleaks<br/>gitleaks-report.json"]
        tv["Trivy<br/>trivy-report.json"]
        sq["SonarQube Cloud<br/>Quality Gate API"]
    end

    subgraph engine ["Security Policy Engine (policy_engine.py)"]
        direction TB
        parse["Per-tool parsers<br/>(parsers/gitleaks.py,<br/>parsers/trivy.py,<br/>parsers/sonarqube.py)"]
        norm["Normalize to a single<br/>Finding schema"]
        eval["policy_evaluator.py<br/>evaluate against policy.yaml"]
        report["report.py<br/>generate security-report.md"]
        parse --> norm --> eval --> report
    end

    policy[["policy.yaml<br/>(version-controlled thresholds:<br/>secrets/critical/high = 0 allowed,<br/>medium/low = unlimited)"]]

    gl --> parse
    tv --> parse
    sq --> parse
    policy -.-> eval

    eval -->|"any threshold exceeded,<br/>OR any input missing/malformed<br/>(fail-closed, AC-05)"| block(["BLOCK<br/>exit code 1"])
    eval -->|"every threshold satisfied"| pass(["PASS<br/>exit code 0"])

    block --> discard["Image discarded<br/>(publish job's if: is false)"]
    pass --> ship["Image published to GHCR,<br/>deployed"]

    report -.->|always uploaded,<br/>PASS or BLOCK| artifact["security-report artifact<br/>(AC-07)"]
    block -.-> slack["Slack notification<br/>(AC-08, every run)"]
    pass -.-> slack

    classDef decision fill:#5b3fd6,stroke:#3d2a99,color:#fff
    class block,pass decision
```

## Why this is fail-closed, not just fail-safe

`policy_evaluator.py`'s outer logic treats **any exception** — a missing report file, a
truncated/malformed JSON payload, a SonarQube API timeout or HTTP error, an unparseable
policy file — as an automatic BLOCK, not a crash. This is unit-tested (27 tests,
`security-policy/tests/test_policy_engine.py`) and live-rehearsed on every
`workflow_dispatch` run via the `policy-gate-negative-rehearsal` job, which exercises 4
distinct failure modes through the real CLI and asserts BLOCK in every case:

| Injected failure | What's tested |
|---|---|
| Malformed Trivy JSON | `json.JSONDecodeError` caught → BLOCK, not a crash |
| Missing Gitleaks report | `FileNotFoundError` caught → BLOCK, not a crash |
| Malformed `policy.yaml` | Unparseable policy → BLOCK, not "no policy = no limits" |
| Unreachable SonarQube host | Connection refused/timeout → BLOCK, not silently skipped |

The same job also re-runs identical inputs 3× (both a PASS case and a BLOCK case) and
byte-compares the decision, stdout, and report (AC-06) — the engine has no hidden
non-determinism (timestamps, ordering, randomness) in its actual decision logic.

## Why Juice Shop itself can never show PASS

Juice Shop is deliberately, organically vulnerable (that's its entire purpose as a
training/test application) — a live scan of `juice-shop/` will always find real
CRITICAL/HIGH findings and secrets. So AC-01/AC-04 ("clean build → PASS") can't be
demonstrated by pointing the real gate at Juice Shop's own code without weakening
`policy.yaml`'s thresholds, which this project treats as off-limits. Instead, the
`policy-gate-pass-rehearsal` job runs the **identical** `policy_engine.py` and
`policy.yaml` against controlled clean fixtures
(`security-policy/tests/fixtures/gitleaks-empty.json`, `clean-trivy.json`,
`sonarqube-passed.json`), proving the PASS path is real and reachable through the same
code path that BLOCKs Juice Shop's own scans every time.
