"""Trivy JSON report -> common Finding schema (SRS FR-31)."""
from __future__ import annotations

import json
from pathlib import Path

from schema import Category, Finding, Severity

_SEVERITY_MAP = {
    "CRITICAL": Severity.CRITICAL,
    "HIGH": Severity.HIGH,
    "MEDIUM": Severity.MEDIUM,
    "LOW": Severity.LOW,
}


def parse(report_path: str | Path) -> list[Finding]:
    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"Trivy report not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if "ArtifactName" not in data:
        raise ValueError(f"Trivy report missing 'ArtifactName': {path}")

    findings = []
    for result in data.get("Results") or []:
        for vuln in result.get("Vulnerabilities") or []:
            raw_severity = (vuln.get("Severity") or "").upper()
            # Fail-closed: an unrecognized/UNKNOWN severity defaults to
            # Critical-equivalent, zero-tolerance (SRS S5.3, fixes the
            # UNKNOWN-bucket gap in the legacy evaluate-trivy.ps1 script --
            # see IMPLEMENTATION_PLAN.md S6.5 FR-33).
            severity = _SEVERITY_MAP.get(raw_severity, Severity.CRITICAL)
            location = f"{result.get('Target', '?')}:{vuln.get('PkgName', '?')}"
            description = f"{vuln.get('VulnerabilityID', '?')}: {vuln.get('Title', '')}".strip()
            findings.append(
                Finding(
                    tool="trivy",
                    category=Category.CONTAINER,
                    severity=severity,
                    location=location,
                    description=description,
                )
            )
    return findings
