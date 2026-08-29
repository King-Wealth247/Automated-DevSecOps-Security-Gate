from pathlib import Path

from parsers import gitleaks, sonarqube, trivy
from schema import Category, Severity

FIXTURES = Path(__file__).parent / "fixtures"


def test_gitleaks_parses_findings_as_secret_critical():
    findings = gitleaks.parse(FIXTURES / "gitleaks-sample.json")
    assert len(findings) == 3
    assert all(f.tool == "gitleaks" for f in findings)
    assert all(f.category == Category.SECRET for f in findings)
    assert all(f.severity == Severity.CRITICAL for f in findings)
    assert findings[0].location == "/repo/juice-shop/data/static/users.yml:88"


def test_gitleaks_empty_array_report():
    findings = gitleaks.parse(FIXTURES / "gitleaks-empty.json")
    assert findings == []


def test_gitleaks_missing_report_raises():
    try:
        gitleaks.parse(FIXTURES / "does-not-exist.json")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_trivy_maps_known_severities_and_defaults_unknown_to_critical():
    findings = trivy.parse(FIXTURES / "trivy-sample.json")
    assert len(findings) == 5
    by_severity = {f.severity: 0 for f in findings}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        assert f.category == Category.CONTAINER
    # 1 declared CRITICAL + 1 UNKNOWN (fail-closed to CRITICAL) = 2
    assert by_severity[Severity.CRITICAL] == 2
    assert by_severity[Severity.HIGH] == 1
    assert by_severity[Severity.MEDIUM] == 1
    assert by_severity[Severity.LOW] == 1


def test_trivy_clean_report_has_no_findings():
    findings = trivy.parse(FIXTURES / "clean-trivy.json")
    assert findings == []


def test_trivy_report_without_artifact_name_raises():
    try:
        trivy.parse(FIXTURES / "gitleaks-sample.json")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_sonarqube_passed_gate_has_no_findings():
    findings = sonarqube.parse_file(FIXTURES / "sonarqube-passed.json")
    assert findings == []


def test_sonarqube_failed_gate_produces_one_finding_per_failed_condition():
    findings = sonarqube.parse_file(FIXTURES / "sonarqube-failed.json")
    assert len(findings) == 1
    assert findings[0].tool == "sonarqube"
    assert findings[0].category == Category.CODE
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].location == "new_security_rating"
