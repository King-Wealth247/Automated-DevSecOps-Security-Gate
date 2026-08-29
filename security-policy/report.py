"""Generates the human-readable security report (SRS S5.6, FR-19/20)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def write_report(out_path: str | Path, decision: str, result=None, error: str | None = None) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# DevSecOps Security Gate Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Decision:** {decision}",
        "",
    ]

    if error:
        lines += ["## Error", "", "```", error, "```", ""]
    elif result is not None:
        lines += ["## Threshold Evaluation", "", "| Category | Found | Allowed | Result |", "|---|---|---|---|"]
        for r in result.threshold_results:
            allowed_display = "unlimited" if r.allowed is None else r.allowed
            status = "BLOCK" if r.blocked else "OK"
            lines.append(f"| {r.label} | {r.count} | {allowed_display} | {status} |")
        lines.append("")

        if result.findings:
            lines += ["## Findings", "", "| Tool | Category | Severity | Location | Description |", "|---|---|---|---|---|"]
            for finding in result.findings:
                description = finding.description.replace("|", "\\|")[:120]
                lines.append(
                    f"| {finding.tool} | {finding.category.value} | {finding.severity.value} "
                    f"| {finding.location} | {description} |"
                )
            lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
