#!/usr/bin/env python3
"""Security Policy Engine entry point (SRS S5, FR-11/FR-14).

Aggregates normalized findings from Gitleaks, Trivy, and SonarQube Cloud,
evaluates them against policy.yaml, and returns a single PASS/BLOCK
decision for the CI/CD pipeline to enforce.

    python policy_engine.py --gitleaks gitleaks-report.json \
        --trivy trivy-report.json \
        --sonar-project-key <key> --sonar-organization <org> \
        --policy policy.yaml --report-out reports/security-report.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

from evaluators.policy_evaluator import evaluate  # noqa: E402
from parsers import gitleaks, sonarqube, trivy  # noqa: E402
from report import write_report  # noqa: E402


def load_policy(policy_path: str | Path) -> dict:
    path = Path(policy_path)
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    if not isinstance(policy, dict) or "security_policy" not in policy:
        raise ValueError(f"Policy file is malformed: missing 'security_policy' root key ({path})")
    return policy


def load_sonarqube_findings(args) -> list:
    sonar_path = Path(args.sonarqube)
    if not sonar_path.exists():
        if not (args.sonar_project_key and args.sonar_organization and args.sonar_token):
            raise RuntimeError(
                f"SonarQube report not found at {sonar_path} and no credentials were "
                "provided to fetch it live (--sonar-project-key/--sonar-organization/--sonar-token)"
            )
        data = sonarqube.fetch(
            args.sonar_project_key, args.sonar_organization, args.sonar_token, args.sonar_host_url
        )
        sonar_path.parent.mkdir(parents=True, exist_ok=True)
        sonar_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return sonarqube.parse_file(sonar_path)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DevSecOps Security Policy Engine")
    parser.add_argument("--gitleaks", required=True, help="Path to Gitleaks JSON report")
    parser.add_argument("--trivy", required=True, help="Path to Trivy JSON report")
    parser.add_argument(
        "--sonarqube",
        default="security-policy/reports/sonarqube-report.json",
        help="Path to a SonarQube Quality Gate JSON report. Fetched live and written "
        "here if missing and --sonar-project-key/--sonar-organization/--sonar-token are set.",
    )
    parser.add_argument("--sonar-project-key", default=os.environ.get("SONAR_PROJECT_KEY"))
    parser.add_argument("--sonar-organization", default=os.environ.get("SONAR_ORGANIZATION"))
    parser.add_argument("--sonar-token", default=os.environ.get("SONAR_TOKEN"))
    parser.add_argument("--sonar-host-url", default=os.environ.get("SONAR_HOST_URL", "https://sonarcloud.io"))
    parser.add_argument("--policy", default="security-policy/policy.yaml", help="Path to policy.yaml")
    parser.add_argument("--report-out", default="security-policy/reports/security-report.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        policy = load_policy(args.policy)
        findings = []
        findings += gitleaks.parse(args.gitleaks)
        findings += trivy.parse(args.trivy)
        findings += load_sonarqube_findings(args)
    except Exception as exc:
        # Fail closed: any error loading the policy or any scanner's output
        # blocks the deployment rather than silently passing (FR-30, NFR-03).
        message = f"{type(exc).__name__}: {exc}"
        print(f"SECURITY GATE: BLOCK (fail-closed)\nERROR: {message}", file=sys.stderr)
        write_report(args.report_out, decision="BLOCK", error=message)
        return 1

    result = evaluate(findings, policy)
    write_report(args.report_out, decision=result.decision, result=result)

    print(f"SECURITY GATE: {result.decision}")
    for r in result.threshold_results:
        marker = "[BLOCK]" if r.blocked else "[OK]"
        allowed_display = "unlimited" if r.allowed is None else r.allowed
        print(f"  {marker} {r.label}: {r.count} found, {allowed_display} allowed")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
