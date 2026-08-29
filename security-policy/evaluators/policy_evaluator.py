"""Evaluates aggregated findings against policy.yaml (SRS S5, FR-13/32/34/35/36)."""
from __future__ import annotations

from dataclasses import dataclass, field

from schema import Category, Finding, Severity

_SEVERITY_POLICY_KEYS = {
    Severity.CRITICAL: "critical_vulnerabilities",
    Severity.HIGH: "high_vulnerabilities",
    Severity.MEDIUM: "medium_vulnerabilities",
    Severity.LOW: "low_vulnerabilities",
}


@dataclass
class ThresholdResult:
    label: str
    count: int
    allowed: int | None  # None = unlimited (not enforced)
    blocked: bool


@dataclass
class EvaluationResult:
    decision: str  # "PASS" or "BLOCK"
    threshold_results: list[ThresholdResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.decision == "PASS"


def evaluate(findings: list[Finding], policy: dict) -> EvaluationResult:
    """Aggregate + evaluate: exactly one PASS/BLOCK decision (FR-14, FR-32)."""
    security_policy = policy.get("security_policy") or {}
    results: list[ThresholdResult] = []

    # Secrets are evaluated as a flat count, not folded into the severity
    # buckets below -- matches how AC-02 / evaluate-gitleaks.ps1 have always
    # treated Gitleaks findings, and the FR-29 example schema's structure.
    secret_findings = [f for f in findings if f.category == Category.SECRET]
    results.append(_check("secrets", len(secret_findings), _allowed(security_policy, "secrets")))

    for severity, key in _SEVERITY_POLICY_KEYS.items():
        count = sum(1 for f in findings if f.category != Category.SECRET and f.severity == severity)
        # A severity with no entry at all in policy.yaml defaults to
        # zero-tolerance (SRS S5.3 fail-closed rule), distinct from an
        # explicit `allowed: null` which means "configured as unlimited".
        allowed = _allowed(security_policy, key, default=0)
        results.append(_check(key, count, allowed))

    decision = "BLOCK" if any(r.blocked for r in results) else "PASS"
    return EvaluationResult(decision=decision, threshold_results=results, findings=findings)


def _allowed(security_policy: dict, key: str, default: int | None = None):
    if key not in security_policy:
        return default
    entry = security_policy[key] or {}
    return entry.get("allowed", default)


def _check(label: str, count: int, allowed) -> ThresholdResult:
    blocked = allowed is not None and count > allowed
    return ThresholdResult(label=label, count=count, allowed=allowed, blocked=blocked)
