from pathlib import Path

import policy_engine

FIXTURES = Path(__file__).parent / "fixtures"


def _run(tmp_path, gitleaks="gitleaks-empty.json", trivy="clean-trivy.json", sonarqube="sonarqube-passed.json"):
    report_out = tmp_path / "security-report.md"
    exit_code = policy_engine.main(
        [
            "--gitleaks", str(FIXTURES / gitleaks),
            "--trivy", str(FIXTURES / trivy),
            "--sonarqube", str(FIXTURES / sonarqube),
            "--policy", str(Path(__file__).parent.parent / "policy.yaml"),
            "--report-out", str(report_out),
        ]
    )
    return exit_code, report_out


def test_clean_inputs_pass_and_exit_zero(tmp_path):
    exit_code, report_out = _run(tmp_path)
    assert exit_code == 0
    assert report_out.exists()
    assert "**Decision:** PASS" in report_out.read_text(encoding="utf-8")


def test_real_findings_block_and_exit_one(tmp_path):
    exit_code, report_out = _run(tmp_path, gitleaks="gitleaks-sample.json", trivy="trivy-sample.json", sonarqube="sonarqube-failed.json")
    assert exit_code == 1
    assert "**Decision:** BLOCK" in report_out.read_text(encoding="utf-8")


def test_missing_policy_file_fails_closed(tmp_path):
    report_out = tmp_path / "security-report.md"
    exit_code = policy_engine.main(
        [
            "--gitleaks", str(FIXTURES / "gitleaks-empty.json"),
            "--trivy", str(FIXTURES / "clean-trivy.json"),
            "--sonarqube", str(FIXTURES / "sonarqube-passed.json"),
            "--policy", str(tmp_path / "does-not-exist.yaml"),
            "--report-out", str(report_out),
        ]
    )
    assert exit_code == 1
    text = report_out.read_text(encoding="utf-8")
    assert "**Decision:** BLOCK" in text
    assert "FileNotFoundError" in text


def test_missing_scanner_report_fails_closed(tmp_path):
    report_out = tmp_path / "security-report.md"
    exit_code = policy_engine.main(
        [
            "--gitleaks", str(tmp_path / "does-not-exist.json"),
            "--trivy", str(FIXTURES / "clean-trivy.json"),
            "--sonarqube", str(FIXTURES / "sonarqube-passed.json"),
            "--policy", str(Path(__file__).parent.parent / "policy.yaml"),
            "--report-out", str(report_out),
        ]
    )
    assert exit_code == 1
    assert "BLOCK" in report_out.read_text(encoding="utf-8")
