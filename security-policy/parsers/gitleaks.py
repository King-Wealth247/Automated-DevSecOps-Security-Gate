"""Gitleaks JSON report -> common Finding schema (SRS FR-31)."""
from __future__ import annotations

import json
from pathlib import Path

from schema import Category, Finding, Severity


def parse(report_path: str | Path) -> list[Finding]:
    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"Gitleaks report not found: {path}")

    raw = path.read_text(encoding="utf-8").strip()
    data = json.loads(raw) if raw else []

    if not isinstance(data, list):
        raise ValueError(f"Gitleaks report is not a JSON array: {path}")

    findings = []
    for entry in data:
        location = f"{entry.get('File', '?')}:{entry.get('StartLine', '?')}"
        description = f"{entry.get('RuleID', 'unknown-rule')}: {entry.get('Description', '')}".strip()
        # Gitleaks doesn't report a severity -- any confirmed secret is
        # treated as Critical (evaluated against `secrets.allowed`, not the
        # vulnerability severity buckets -- see evaluators/policy_evaluator.py).
        findings.append(
            Finding(
                tool="gitleaks",
                category=Category.SECRET,
                severity=Severity.CRITICAL,
                location=location,
                description=description,
            )
        )
    return findings
