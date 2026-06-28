from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a GitHub Actions summary for release smoke output.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--summary-output")
    args = parser.parse_args()

    summary = render_release_smoke_summary(Path(args.report))
    summary_output = args.summary_output or os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_output:
        with Path(summary_output).open("a", encoding="utf-8") as handle:
            handle.write(summary)
    else:
        print(summary, end="")


def render_release_smoke_summary(report_path: Path) -> str:
    lines = ["## Release smoke", ""]
    if not report_path.exists():
        lines.extend(["Release smoke report was not generated.", ""])
        return "\n".join(lines)

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        lines.extend([f"Release smoke report could not be parsed: `{exc.msg}`.", ""])
        return "\n".join(lines)
    if not isinstance(report, dict):
        lines.extend(["Release smoke report was not a JSON object.", ""])
        return "\n".join(lines)
    checks = _mapping(report.get("checks"))
    eval_checks = _mapping(checks.get("eval_checks"))
    deployment_checks = _mapping(checks.get("deployment_checks"))
    manifest = _mapping(report.get("manifest"))
    report_output = _mapping(report.get("report"))
    lines.extend(
        [
            f"- Result: `{'pass' if report.get('ok') is True else 'fail'}`",
            f"- Wheel: `{report.get('wheel', 'unknown')}`",
            f"- Source: `{manifest.get('source_branch') or 'detached'}@{manifest.get('source_commit') or 'unknown'}`",
            f"- Source clean: `{checks.get('source_clean', 'not-required')}`",
            f"- Eval checks: `{eval_checks.get('passed', '?')}/{eval_checks.get('total', '?')}` passed",
            f"- Deployment checks: `{deployment_checks.get('passed', '?')}/{deployment_checks.get('total', '?')}` passed",
            f"- Secret hygiene: `{checks.get('secret_hygiene')}`",
            f"- Report output written: `{report_output.get('written', False)}`",
            (
                "- Manifest sidecar: "
                f"`written={manifest.get('manifest_written', False)}, "
                f"matches={manifest.get('manifest_payload_matches_output', '?')}`"
            ),
            (
                "- SBOM sidecar: "
                f"`written={manifest.get('sbom_written', False)}, "
                f"matches={manifest.get('sbom_payload_matches_output', '?')}`"
            ),
            f"- Manifest SHA-256: `{manifest.get('manifest_sha256', 'unknown')}`",
            f"- SBOM SHA-256: `{manifest.get('sbom_sha256', 'unknown')}`",
            "",
        ]
    )
    return "\n".join(lines)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    main()
