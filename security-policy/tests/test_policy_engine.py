import urllib.error
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


def test_malformed_scanner_report_fails_closed(tmp_path):
    exit_code, report_out = _run(tmp_path, trivy="malformed-trivy.json")
    assert exit_code == 1
    text = report_out.read_text(encoding="utf-8")
    assert "**Decision:** BLOCK" in text
    assert "JSONDecodeError" in text


def _run_with_sonar_fetch(tmp_path, monkeypatch, fetch_side_effect):
    """Runs the engine with a SonarQube report that doesn't exist yet, forcing
    the live-fetch path, with urlopen replaced by `fetch_side_effect`."""
    monkeypatch.setattr(policy_engine.sonarqube.urllib.request, "urlopen", fetch_side_effect)
    report_out = tmp_path / "security-report.md"
    exit_code = policy_engine.main(
        [
            "--gitleaks", str(FIXTURES / "gitleaks-empty.json"),
            "--trivy", str(FIXTURES / "clean-trivy.json"),
            "--sonarqube", str(tmp_path / "not-fetched-yet.json"),
            "--sonar-project-key", "k",
            "--sonar-organization", "o",
            "--sonar-token", "t",
            "--policy", str(Path(__file__).parent.parent / "policy.yaml"),
            "--report-out", str(report_out),
        ]
    )
    return exit_code, report_out.read_text(encoding="utf-8")


def test_sonarqube_timeout_fails_closed(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise TimeoutError("timed out")

    exit_code, text = _run_with_sonar_fetch(tmp_path, monkeypatch, timeout)
    assert exit_code == 1
    assert "**Decision:** BLOCK" in text
    assert "TimeoutError" in text


def test_sonarqube_http_401_fails_closed(tmp_path, monkeypatch):
    def unauthorized(request, *args, **kwargs):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    # Mirrors the real 2026-09-25 incident (revoked SONAR_TOKEN -> 401): a
    # broken scanner credential must BLOCK, never silently pass.
    exit_code, text = _run_with_sonar_fetch(tmp_path, monkeypatch, unauthorized)
    assert exit_code == 1
    assert "Failed to fetch SonarQube Quality Gate status" in text
    assert "401" in text


def _normalized(report_out):
    # "Generated" is the only intentionally time-varying line in the report.
    return [l for l in report_out.read_text(encoding="utf-8").splitlines() if not l.startswith("**Generated:**")]


def test_engine_is_deterministic_across_repeated_runs(tmp_path, capsys):
    # AC-06 through the real entry point (not just the pure evaluator): same
    # inputs + same policy, run 3x -> identical decision, stdout and report.
    results = []
    for _ in range(3):
        exit_code, report_out = _run(
            tmp_path, gitleaks="gitleaks-sample.json", trivy="trivy-sample.json", sonarqube="sonarqube-failed.json"
        )
        results.append((exit_code, capsys.readouterr().out, _normalized(report_out)))
    assert results[0] == results[1] == results[2]
    assert results[0][0] == 1


def test_output_reports_findings_by_tool(tmp_path, capsys):
    _run(tmp_path, gitleaks="gitleaks-sample.json", trivy="trivy-sample.json", sonarqube="sonarqube-failed.json")
    out = capsys.readouterr().out
    assert "findings by tool: gitleaks=3, trivy=5, sonarqube=1" in out


def test_findings_by_tool_lists_every_adapter_even_when_zero(tmp_path, capsys):
    _run(tmp_path)
    assert "findings by tool: gitleaks=0, trivy=0, sonarqube=0" in capsys.readouterr().out
