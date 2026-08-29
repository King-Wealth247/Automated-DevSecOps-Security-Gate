import yaml

from evaluators.policy_evaluator import evaluate
from schema import Category, Finding, Severity

CALIBRATED_POLICY = yaml.safe_load(
    """
security_policy:
  secrets:
    allowed: 0
  critical_vulnerabilities:
    allowed: 0
  high_vulnerabilities:
    allowed: 0
  medium_vulnerabilities:
    allowed: null
  low_vulnerabilities:
    allowed: null
"""
)


def _finding(category, severity, n=1):
    return [
        Finding(tool="test", category=category, severity=severity, location=f"loc{i}", description="d")
        for i in range(n)
    ]


def test_clean_run_passes():
    result = evaluate([], CALIBRATED_POLICY)
    assert result.decision == "PASS"
    assert result.passed


def test_any_secret_blocks_under_zero_tolerance():
    findings = _finding(Category.SECRET, Severity.CRITICAL, 1)
    result = evaluate(findings, CALIBRATED_POLICY)
    assert result.decision == "BLOCK"


def test_any_critical_vulnerability_blocks():
    findings = _finding(Category.CONTAINER, Severity.CRITICAL, 1)
    result = evaluate(findings, CALIBRATED_POLICY)
    assert result.decision == "BLOCK"


def test_medium_and_low_never_block_when_unlimited():
    findings = _finding(Category.CONTAINER, Severity.MEDIUM, 100) + _finding(Category.CONTAINER, Severity.LOW, 100)
    result = evaluate(findings, CALIBRATED_POLICY)
    assert result.decision == "PASS"


def test_realistic_juice_shop_baseline_blocks():
    # Matches the CI-validated 2026-08-27 baseline: 8 CRITICAL, 38 HIGH,
    # 36 MEDIUM, 11 LOW Trivy findings + 69 Gitleaks secrets.
    findings = (
        _finding(Category.SECRET, Severity.CRITICAL, 69)
        + _finding(Category.CONTAINER, Severity.CRITICAL, 8)
        + _finding(Category.CONTAINER, Severity.HIGH, 38)
        + _finding(Category.CONTAINER, Severity.MEDIUM, 36)
        + _finding(Category.CONTAINER, Severity.LOW, 11)
    )
    result = evaluate(findings, CALIBRATED_POLICY)
    assert result.decision == "BLOCK"
    labels_blocked = {r.label for r in result.threshold_results if r.blocked}
    assert labels_blocked == {"secrets", "critical_vulnerabilities", "high_vulnerabilities"}


def test_exact_threshold_boundary_passes():
    policy = yaml.safe_load(
        "security_policy:\n  high_vulnerabilities:\n    allowed: 2\n"
    )
    findings = _finding(Category.CONTAINER, Severity.HIGH, 2)
    result = evaluate(findings, policy)
    assert result.decision == "PASS"


def test_one_over_threshold_blocks():
    policy = yaml.safe_load(
        "security_policy:\n  high_vulnerabilities:\n    allowed: 2\n"
    )
    findings = _finding(Category.CONTAINER, Severity.HIGH, 3)
    result = evaluate(findings, policy)
    assert result.decision == "BLOCK"


def test_missing_severity_key_defaults_to_zero_tolerance():
    # medium_vulnerabilities has no entry at all in this minimal policy --
    # SRS S5.3's fail-closed default for unmapped severities applies.
    policy = yaml.safe_load("security_policy:\n  secrets:\n    allowed: 0\n")
    findings = _finding(Category.CONTAINER, Severity.MEDIUM, 1)
    result = evaluate(findings, policy)
    assert result.decision == "BLOCK"


def test_deterministic_repeated_evaluation():
    # AC-06: same inputs + same policy -> identical decision, run 3x.
    findings = _finding(Category.SECRET, Severity.CRITICAL, 1)
    decisions = {evaluate(findings, CALIBRATED_POLICY).decision for _ in range(3)}
    assert decisions == {"BLOCK"}
