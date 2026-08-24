# Automated DevSecOps Security Gate

**Security-First CI/CD Deployment Gate**

An automated, policy-driven security gate that integrates secret scanning, static code analysis, and container vulnerability scanning into a CI/CD pipeline and enforces a deterministic **PASS/BLOCK** deployment decision based on a version-controlled security policy — removing the manual "read three scanner reports and decide" step from the release process.

> Full requirements, scope, and schedule live in [`SRS_DevSecOps_Security_Gate.pdf`](./SRS_DevSecOps_Security_Gate.pdf) and [`Cahier_des_Charges_EN_DevSecOps_Security_Gate.pdf`](./Cahier_des_Charges_EN_DevSecOps_Security_Gate.pdf). Current build status and remaining work are tracked in [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

## Purpose

CI/CD pipelines automate build, test, and deployment — but the decision of whether a build is *safe enough to ship* is usually still made by a person, manually, after reading several differently-formatted scanner reports. This project closes that gap: it does not build new scanners, it **enforces** the combined output of existing ones (Gitleaks, SonarQube Cloud, Trivy) as a single, automatic, unavoidable deployment gate.

[OWASP Juice Shop](https://owasp-juice.shop/) — an open-source, intentionally vulnerable web application — is used unmodified as the test subject to validate the gate against realistic findings. Juice Shop is **not** the deliverable; the CI/CD workflows and the Security Policy Engine are.

## Architecture

```
Developer → GitHub (push / PR)
    → GitHub Actions
        → Build / Test
        → Docker image build (Juice Shop)
        → Security Scanners (parallel: Gitleaks · SonarQube Cloud · Trivy)
            → Security Policy Engine (normalize → evaluate policy.yaml → decide)
                → PASS → tag & push image to GHCR → deploy to AWS EC2 → Slack: approved
                → BLOCK → discard image → Slack: blocked + report
```

## Repository Structure

```
DevSecOps-Pipeline/
├── .github/workflows/     GitHub Actions CI/CD pipeline definitions
├── juice-shop/             OWASP Juice Shop test application (vendored, unmodified)
├── security-gate/          Security policy + evaluation scripts (Security Policy Engine)
│   ├── policy/              Version-controlled security policy
│   ├── scripts/              Policy evaluation logic
│   └── tests/                 Fixtures and test cases
├── reports/                Generated scan/security reports (local, gitignored)
├── docs/                    Project documentation
├── .gitleaks.toml           Gitleaks secret-scanning configuration
├── IMPLEMENTATION_PLAN.md   Requirements-to-implementation status and roadmap
└── README.md
```

## Prerequisites

| Tool | Purpose |
|---|---|
| [Git](https://git-scm.com/) | Version control |
| [Docker](https://www.docker.com/) | Build and run the Juice Shop container image |
| [PowerShell](https://learn.microsoft.com/powershell/) / Python 3.x | Run the security gate evaluation scripts |
| [Trivy](https://trivy.dev/) | Container/dependency vulnerability scanning |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | Secret scanning |
| A GitHub account | CI/CD, Container Registry |
| A SonarQube Cloud account | Static application security testing |
| A Slack workspace | Pipeline notifications |
| An AWS account (free-tier eligible) | Test deployment target |

Locally verified tool versions are recorded in [`docs/DEVELOPMENT ENVIRONMENT.md`](./docs/DEVELOPMENT%20ENVIRONMENT.md).

## Local Setup

```bash
# Clone the repository (Juice Shop is vendored into juice-shop/, no separate clone needed)
git clone https://github.com/King-Wealth247/Automated-DevSecOps-Security-Gate.git
cd DevSecOps-Pipeline

# Build the Juice Shop test application image
docker build -t devsecops-juice-shop:local ./juice-shop

# Run it locally
docker run --rm -p 3000:3000 devsecops-juice-shop:local
# → http://localhost:3000
```

## Security Scanning

| Scanner | What it checks | Config |
|---|---|---|
| **Gitleaks** | Exposed secrets/credentials in the repository, including Juice Shop's own source | [`.gitleaks.toml`](./.gitleaks.toml) |
| **SonarQube Cloud** | Security-focused static code analysis of Juice Shop's source | *(pending — see `IMPLEMENTATION_PLAN.md`)* |
| **Trivy** | Known CVEs in the built container image and its dependencies | [`security-gate/policy/security-policy.json`](./security-gate/policy/security-policy.json) |

Run scans locally:

```powershell
# Gitleaks — writes/expects a report at reports\gitleaks\final.json
gitleaks detect --source . --config .gitleaks.toml --report-path reports\gitleaks\final.json

# Trivy — scan the built image
trivy image --format json --output reports\trivy\baseline.json devsecops-juice-shop:local
```

## Security Policy & the PASS/BLOCK Gate

Security policy is defined in a version-controlled configuration file specifying the maximum number of allowed findings per severity level (Critical, High, Medium, Low). The gate evaluates every scanner's findings against this policy and produces exactly one decision per run:

- **PASS** — every configured threshold is satisfied → the image is tagged, pushed to GitHub Container Registry, and deployed to the AWS test environment.
- **BLOCK** — any threshold is exceeded, or a scanner's output is missing/malformed (**fail-closed**) → the image is discarded and the pipeline run ends in a failed state.

Evaluate a scan against the current policy locally:

```powershell
.\security-gate\scripts\evaluate-trivy.ps1 -ReportPath ".\reports\trivy\baseline.json"
.\security-gate\scripts\evaluate-gitleaks.ps1 -ReportPath ".\reports\gitleaks\final.json"
```

An exit code of `0` means PASS; a non-zero exit code means BLOCK.

## Running Tests

Fixture-based test data lives under `security-gate/tests/fixtures/`. See [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) for the planned automated policy/integration test suite.

## CI/CD & Deployment

On every push or pull request, the pipeline is intended to: build and test Juice Shop → build its Docker image → run all three scanners in parallel → evaluate the combined findings against policy → on PASS, publish to GHCR and deploy to a single AWS EC2 test instance via an OIDC-federated IAM role (no long-lived AWS credentials); on BLOCK, stop the pipeline. Every run generates a human-readable security report (pipeline artifact) and a Slack notification. See `IMPLEMENTATION_PLAN.md` for what is currently implemented versus planned.

## Project Status

This project follows a 4-week implementation plan. For a detailed breakdown of what is complete, in progress, or not yet started — mapped against every requirement in the SRS and Cahier des Charges — see [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

## License

The OWASP Juice Shop test application (`juice-shop/`) is used unmodified under its own MIT license. See [`juice-shop/LICENSE`](./juice-shop/LICENSE).
