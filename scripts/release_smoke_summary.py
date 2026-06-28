from __future__ import annotations

import argparse
import json
import os
import re
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
        lines.extend([f"Release smoke report could not be parsed: {_inline_code(exc.msg)}.", ""])
        return "\n".join(lines)
    if not isinstance(report, dict):
        lines.extend(["Release smoke report was not a JSON object.", ""])
        return "\n".join(lines)
    checks = _mapping(report.get("checks"))
    eval_checks = _mapping(checks.get("eval_checks"))
    deployment_checks = _mapping(checks.get("deployment_checks"))
    manifest = _mapping(report.get("manifest"))
    report_output = _mapping(report.get("report"))
    source = f"{manifest.get('source_branch') or 'detached'}@{manifest.get('source_commit') or 'unknown'}"
    ci_context = _ci_context(manifest)
    ci_run = _ci_run(manifest)
    eval_count = f"{eval_checks.get('passed', '?')}/{eval_checks.get('total', '?')}"
    deployment_count = f"{deployment_checks.get('passed', '?')}/{deployment_checks.get('total', '?')}"
    source_dirty_status = (
        f"count={manifest.get('source_dirty_count', 'unknown')}, "
        f"paths_truncated={manifest.get('source_dirty_paths_truncated', 'unknown')}"
    )
    dependency_status = (
        f"count={manifest.get('dependency_count', 'unknown')}, "
        f"pinned={manifest.get('direct_dependencies_pinned', 'unknown')}"
    )
    build_environment = (
        f"python={manifest.get('build_python_version', 'unknown')}, "
        f"platform={manifest.get('build_platform', 'unknown')}"
    )
    package_license = (
        f"declared={manifest.get('license_declared', 'unknown')}, "
        f"check={checks.get('package_license', 'unknown')}"
    )
    manifest_sidecar = (
        f"written={manifest.get('manifest_written', False)}, "
        f"matches={manifest.get('manifest_payload_matches_output', '?')}"
    )
    sbom_sidecar = (
        f"written={manifest.get('sbom_written', False)}, "
        f"matches={manifest.get('sbom_payload_matches_output', '?')}"
    )
    lines.extend(
        [
            f"- Result: {_inline_code('pass' if report.get('ok') is True else 'fail')}",
            f"- Wheel: {_inline_code(report.get('wheel', 'unknown'))}",
            f"- Wheel SHA-256: {_inline_code(manifest.get('wheel_sha256', 'unknown'))}",
            f"- Wheel size bytes: {_inline_code(manifest.get('wheel_size_bytes', 'unknown'))}",
            f"- Source: {_inline_code(source)}",
            f"- CI context: {_inline_code(ci_context)}",
            f"- CI run: {_inline_code(ci_run)}",
            f"- Source clean: {_inline_code(checks.get('source_clean', 'not-required'))}",
            f"- Source dirty paths: {_inline_code(source_dirty_status)}",
            f"- Eval checks: {_inline_code(eval_count)} passed",
            f"- Deployment checks: {_inline_code(deployment_count)} passed",
            f"- Dependencies: {_inline_code(dependency_status)}",
            f"- Build environment: {_inline_code(build_environment)}",
            f"- Package license: {_inline_code(package_license)}",
            f"- Secret hygiene: {_inline_code(checks.get('secret_hygiene'))}",
            f"- Report output written: {_inline_code(report_output.get('written', False))}",
            f"- Manifest sidecar: {_inline_code(manifest_sidecar)}",
            f"- SBOM sidecar: {_inline_code(sbom_sidecar)}",
            f"- Manifest SHA-256: {_inline_code(manifest.get('manifest_sha256', 'unknown'))}",
            f"- SBOM SHA-256: {_inline_code(manifest.get('sbom_sha256', 'unknown'))}",
            "",
        ]
    )
    return "\n".join(lines)


def _ci_context(manifest: dict[str, Any]) -> str:
    provider = manifest.get("ci_provider") or "local"
    repository = manifest.get("ci_repository")
    ref = manifest.get("ci_ref")
    if provider == "local" and not repository and not ref:
        return "local"
    return f"{provider}:{repository or 'unknown'}@{ref or 'unknown'}"


def _ci_run(manifest: dict[str, Any]) -> str:
    run = manifest.get("ci_run_url") or manifest.get("ci_run_id") or "not-applicable"
    attempt = manifest.get("ci_run_attempt")
    if attempt:
        return f"{run} attempt={attempt}"
    return str(run)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _inline_code(value: Any) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    max_backticks = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    delimiter = "`" * (max_backticks + 1)
    if max_backticks:
        return f"{delimiter} {text} {delimiter}"
    return f"{delimiter}{text}{delimiter}"


if __name__ == "__main__":
    main()
