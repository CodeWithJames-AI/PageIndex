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
    ci_workflow = (
        f"name={manifest.get('ci_workflow') or 'unknown'}, "
        f"sha={manifest.get('ci_sha') or 'unknown'}"
    )
    eval_count = f"{eval_checks.get('passed', '?')}/{eval_checks.get('total', '?')}"
    deployment_count = f"{deployment_checks.get('passed', '?')}/{deployment_checks.get('total', '?')}"
    packaging_gates = (
        f"wheel_built={checks.get('wheel_built', 'unknown')}, "
        f"console_script={checks.get('console_script', 'unknown')}, "
        f"manifest_generated={checks.get('manifest_generated', 'unknown')}"
    )
    command_gates = (
        f"eval_ok={checks.get('eval_command', 'unknown')}, "
        f"deployment_ok={manifest.get('deployment_check_ok', checks.get('deployment_check', 'unknown'))}, "
        f"deployment_failed={manifest.get('deployment_check_failed', deployment_checks.get('failed', 'unknown'))}"
    )
    artifact_identity = (
        f"count={manifest.get('artifact_count', 'unknown')}, "
        f"type={manifest.get('artifact_type', 'unknown')}, "
        f"media_type={manifest.get('artifact_media_type', 'unknown')}"
    )
    artifact_gates = (
        f"identity={checks.get('artifact_identity', 'unknown')}, "
        f"manifest_sidecar={checks.get('manifest_sidecar_integrity', 'unknown')}, "
        f"manifest_timestamp={checks.get('manifest_timestamp', 'unknown')}, "
        f"sbom_sidecar={checks.get('sbom_sidecar_integrity', 'unknown')}"
    )
    wheel_integrity = (
        f"content_ok={manifest.get('wheel_content_policy_ok', checks.get('wheel_content_policy', 'unknown'))}, "
        f"record_ok={manifest.get('wheel_record_hashes_valid', checks.get('wheel_record_hashes', 'unknown'))}"
    )
    source_dirty_status = (
        f"count={manifest.get('source_dirty_count', 'unknown')}, "
        f"paths_truncated={manifest.get('source_dirty_paths_truncated', 'unknown')}"
    )
    dependency_status = (
        f"count={manifest.get('dependency_count', 'unknown')}, "
        f"pinned={manifest.get('direct_dependencies_pinned', 'unknown')}"
    )
    dependency_gates = (
        f"inventory={checks.get('dependency_inventory', 'unknown')}, "
        f"pins={checks.get('dependency_pins', 'unknown')}"
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
    sidecar_sizes = (
        f"manifest_bytes={manifest.get('manifest_size_bytes', 'unknown')}, "
        f"sbom_bytes={manifest.get('sbom_size_bytes', 'unknown')}"
    )
    manifest_generator = (
        f"name={manifest.get('manifest_generator', 'unknown')}, "
        f"version={manifest.get('manifest_generator_version', 'unknown')}, "
        f"schema={manifest.get('manifest_schema', 'unknown')}, "
        f"check={checks.get('manifest_generator', 'unknown')}"
    )
    sbom_sidecar = (
        f"written={manifest.get('sbom_written', False)}, "
        f"matches={manifest.get('sbom_payload_matches_output', '?')}"
    )
    sbom_gates = (
        f"generated={checks.get('sbom_generated', 'unknown')}, "
        f"describes_root={checks.get('sbom_describes_root', 'unknown')}, "
        f"package_urls={checks.get('sbom_package_urls', 'unknown')}"
    )
    sbom_inventory = (
        f"components={manifest.get('sbom_component_count', 'unknown')}, "
        f"external_refs={manifest.get('sbom_external_ref_count', 'unknown')}, "
        f"describes={manifest.get('sbom_describes_count', 'unknown')}"
    )
    sbom_root_supplier = (
        f"supplier={manifest.get('sbom_root_supplier', 'unknown')}, "
        f"check={checks.get('sbom_root_supplier', 'unknown')}"
    )
    lines.extend(
        [
            f"- Result: {_inline_code('pass' if report.get('ok') is True else 'fail')}",
            f"- Created at: {_inline_code(manifest.get('created_at', 'unknown'))}",
            f"- Wheel: {_inline_code(report.get('wheel', 'unknown'))}",
            f"- Wheel SHA-256: {_inline_code(manifest.get('wheel_sha256', 'unknown'))}",
            f"- Wheel size bytes: {_inline_code(manifest.get('wheel_size_bytes', 'unknown'))}",
            f"- Artifact identity: {_inline_code(artifact_identity)}",
            f"- Artifact gates: {_inline_code(artifact_gates)}",
            f"- Packaging gates: {_inline_code(packaging_gates)}",
            f"- Wheel integrity: {_inline_code(wheel_integrity)}",
            f"- Source: {_inline_code(source)}",
            f"- Source upstream: {_inline_code(manifest.get('source_upstream') or 'unknown')}",
            f"- CI context: {_inline_code(ci_context)}",
            f"- CI run: {_inline_code(ci_run)}",
            f"- CI workflow: {_inline_code(ci_workflow)}",
            f"- Source clean: {_inline_code(checks.get('source_clean', 'not-required'))}",
            f"- Source clean required: {_inline_code(manifest.get('source_clean_required', 'unknown'))}",
            f"- Source dirty: {_inline_code(manifest.get('source_dirty', 'unknown'))}",
            f"- Source dirty paths: {_inline_code(source_dirty_status)}",
            f"- Eval checks: {_inline_code(eval_count)} passed",
            f"- Deployment checks: {_inline_code(deployment_count)} passed",
            f"- Command gates: {_inline_code(command_gates)}",
            f"- Dependencies: {_inline_code(dependency_status)}",
            f"- Dependency gates: {_inline_code(dependency_gates)}",
            f"- Build environment: {_inline_code(build_environment)}",
            f"- Package license: {_inline_code(package_license)}",
            f"- Secret hygiene: {_inline_code(checks.get('secret_hygiene'))}",
            f"- Secret hygiene findings: {_inline_code(manifest.get('secret_hygiene_finding_count', 'unknown'))}",
            f"- Report output written: {_inline_code(report_output.get('written', False))}",
            f"- Manifest sidecar: {_inline_code(manifest_sidecar)}",
            f"- Sidecar sizes: {_inline_code(sidecar_sizes)}",
            f"- Manifest generator: {_inline_code(manifest_generator)}",
            f"- SBOM sidecar: {_inline_code(sbom_sidecar)}",
            f"- SBOM gates: {_inline_code(sbom_gates)}",
            f"- SBOM inventory: {_inline_code(sbom_inventory)}",
            f"- SBOM root supplier: {_inline_code(sbom_root_supplier)}",
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
