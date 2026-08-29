"""SonarQube Cloud Quality Gate -> common Finding schema (SRS FR-31).

Unlike Gitleaks/Trivy, SonarQube's result isn't a file the CI job already
saves to disk -- `fetch()` queries the same Quality Gate API endpoint the
already-validated evaluate-sonarqube.ps1 script uses. It must only be called
after the analysis's background task has finished, which the CI workflow's
SonarSource/sonarqube-quality-gate-action wait step already guarantees
before the policy engine runs.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from schema import Category, Finding, Severity


def fetch(project_key: str, organization: str, token: str,
          host_url: str = "https://sonarcloud.io") -> dict:
    query = urllib.parse.urlencode({"projectKey": project_key, "organization": organization})
    url = f"{host_url}/api/qualitygates/project_status?{query}"
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch SonarQube Quality Gate status: {exc}") from exc


def parse(data: dict) -> list[Finding]:
    project_status = data.get("projectStatus")
    if project_status is None:
        raise ValueError("SonarQube report missing 'projectStatus'")

    findings = []
    for condition in project_status.get("conditions", []):
        if condition.get("status") == "OK":
            continue
        metric = condition.get("metricKey", "unknown_metric")
        actual = condition.get("actualValue", "?")
        threshold = condition.get("errorThreshold", "?")
        # A failed new-code Quality Gate condition is inherently blocking --
        # there is no per-issue severity at this level of the API, so it is
        # classified Critical (category "code", separate from Trivy's
        # "container" findings).
        findings.append(
            Finding(
                tool="sonarqube",
                category=Category.CODE,
                severity=Severity.CRITICAL,
                location=metric,
                description=(
                    f"Quality Gate condition failed: {metric} "
                    f"(actual={actual}, threshold={threshold})"
                ),
            )
        )
    return findings


def parse_file(report_path: str | Path) -> list[Finding]:
    path = Path(report_path)
    if not path.exists():
        raise FileNotFoundError(f"SonarQube report not found: {path}")
    return parse(json.loads(path.read_text(encoding="utf-8")))
