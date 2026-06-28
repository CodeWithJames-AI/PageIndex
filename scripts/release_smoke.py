from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from email.parser import Parser
from pathlib import Path
from typing import Any


PACKAGE_NAME = "pageindex_enterprise_cleanroom"
VERSION = "0.1.0"
SOURCE_DIRTY_PATH_LIMIT = 50
SECRET_SHAPED_PATTERNS = {
    "api_token": re.compile(r"\bpit_[A-Za-z0-9_-]{20,}\b"),
    "document_share_token": re.compile(r"\bpis_[A-Za-z0-9_-]{20,}\b"),
    "conversation_share_token": re.compile(r"\bpcs_[A-Za-z0-9_-]{20,}\b"),
    "source_set_share_token": re.compile(r"\bpss_[A-Za-z0-9_-]{20,}\b"),
    "provider_api_key": re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and smoke-test the PageIndex enterprise wheel.")
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest-output")
    parser.add_argument("--sbom-output")
    parser.add_argument("--require-clean-source", action="store_true")
    args = parser.parse_args()
    report = run_release_smoke(
        Path(args.repo_root),
        manifest_output=Path(args.manifest_output) if args.manifest_output else None,
        sbom_output=Path(args.sbom_output) if args.sbom_output else None,
        require_clean_source=args.require_clean_source,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    exit_code = _release_smoke_exit_code(report)
    if exit_code:
        raise SystemExit(exit_code)


def run_release_smoke(
    repo_root: Path,
    *,
    manifest_output: Path | None = None,
    sbom_output: Path | None = None,
    require_clean_source: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="pageindex-release-smoke-") as tmp:
        tmp_path = Path(tmp)
        wheel_dir = tmp_path / "wheels"
        install_dir = tmp_path / "install"
        deployment_root = tmp_path / "deployment-root"
        eval_root = tmp_path / "eval-root"
        wheel_dir.mkdir()
        install_dir.mkdir()

        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                str(repo_root),
                "--no-deps",
                "--no-build-isolation",
                "-w",
                str(wheel_dir),
            ],
            cwd=repo_root,
        )
        wheel = _single_wheel(wheel_dir)
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(install_dir),
                str(wheel),
            ],
            cwd=tmp_path,
        )

        console = install_dir / "bin" / "pageindex-enterprise"
        if not console.exists():
            raise AssertionError(f"console script missing: {console}")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(install_dir) + os.pathsep + env.get("PYTHONPATH", "")
        help_result = _run([str(console), "--help"], cwd=tmp_path, env=env)
        eval_result = _run(
            [
                str(console),
                "--root",
                str(eval_root),
                "eval",
                "--fixtures-root",
                str(repo_root),
            ],
            cwd=tmp_path,
            env=env,
        )
        eval_report = json.loads(eval_result.stdout)
        deployment_report = _run_packaged_deployment_check(console, deployment_root, cwd=tmp_path, env=env)
        _inspect_wheel(wheel)
        package_metadata = _wheel_package_metadata(wheel)
        dependencies = _wheel_dependencies(wheel)
        dependency_policy = _dependency_policy(dependencies)
        wheel_record = _wheel_record_integrity(wheel)
        wheel_content = _wheel_content_policy(wheel)
        manifest = _artifact_manifest(
            wheel,
            package_metadata=package_metadata,
            build_environment=_build_environment(),
            source=_source_metadata(repo_root),
            dependencies=dependencies,
            dependency_policy=dependency_policy,
            wheel_record=wheel_record,
            wheel_content=wheel_content,
        )
        sbom = _sbom_document(manifest)
        secret_hygiene = _release_secret_hygiene(
            {
                "console_help_stdout": help_result.stdout,
                "console_help_stderr": help_result.stderr,
                "eval_stdout": eval_result.stdout,
                "eval_stderr": eval_result.stderr,
                "deployment_report": json.dumps(deployment_report, sort_keys=True),
                "artifact_manifest": json.dumps(manifest, sort_keys=True),
                "sbom": json.dumps(sbom, sort_keys=True),
            }
        )
        if manifest_output is not None:
            manifest_output = manifest_output.expanduser().resolve()
            manifest_output.parent.mkdir(parents=True, exist_ok=True)
            manifest_output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if sbom_output is not None:
            sbom_output = sbom_output.expanduser().resolve()
            sbom_output.parent.mkdir(parents=True, exist_ok=True)
            sbom_output.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        checks = {
            "wheel_built": wheel.name == f"{PACKAGE_NAME}-{VERSION}-py3-none-any.whl",
            "console_script": "usage:" in help_result.stdout and "eval" in help_result.stdout,
            "manifest_generated": len(manifest["artifacts"]) == 1 and len(manifest["artifacts"][0]["sha256"]) == 64,
            "sbom_generated": len(sbom["packages"]) == len(dependencies) + 1,
            "build_environment": _build_environment_ok(manifest["build_environment"]),
            "dependency_inventory": bool(manifest["dependencies"]),
            "dependency_pins": manifest["dependency_policy"]["direct_dependencies_pinned"],
            "package_license": manifest["package"]["license_declared"] != "NOASSERTION",
            "wheel_content_policy": manifest["artifacts"][0]["content"]["ok"],
            "wheel_record_hashes": manifest["artifacts"][0]["record"]["ok"],
            "eval_command": eval_report.get("ok") is True,
            "eval_checks": eval_report.get("summary", {}),
            "deployment_check": deployment_report.get("ok") is True,
            "deployment_checks": deployment_report.get("summary", {}),
            "secret_hygiene": secret_hygiene["ok"],
        }
        if require_clean_source:
            checks["source_clean"] = manifest["source"]["dirty"] is False
        report = {
            "ok": _release_checks_ok(checks),
            "wheel": wheel.name,
            "manifest": {
                "artifact_count": len(manifest["artifacts"]),
                "build_platform": manifest["build_environment"]["platform"],
                "build_python_version": manifest["build_environment"]["python_version"],
                "dependency_count": len(manifest["dependencies"]),
                "direct_dependencies_pinned": manifest["dependency_policy"]["direct_dependencies_pinned"],
                "license_declared": manifest["package"]["license_declared"],
                "path": str(manifest_output) if manifest_output is not None else None,
                "sbom_component_count": len(sbom["packages"]),
                "sbom_path": str(sbom_output) if sbom_output is not None else None,
                "source_clean_required": require_clean_source,
                "source_branch": manifest["source"]["branch"],
                "source_commit": manifest["source"]["commit"],
                "source_dirty": manifest["source"]["dirty"],
                "source_dirty_count": manifest["source"]["dirty_count"],
                "source_dirty_paths_truncated": manifest["source"]["dirty_paths_truncated"],
                "source_upstream": manifest["source"]["upstream"],
                "deployment_check_ok": deployment_report.get("ok") is True,
                "deployment_check_failed": deployment_report.get("summary", {}).get("failed"),
                "secret_hygiene_finding_count": secret_hygiene["finding_count"],
                "secret_hygiene_ok": secret_hygiene["ok"],
                "wheel_content_policy_ok": manifest["artifacts"][0]["content"]["ok"],
                "wheel_record_hashes_valid": manifest["artifacts"][0]["record"]["ok"],
                "wheel_sha256": manifest["artifacts"][0]["sha256"],
                "wheel_size_bytes": manifest["artifacts"][0]["size_bytes"],
            },
            "checks": checks,
        }
        report_secret_hygiene = _release_secret_hygiene({"release_report": json.dumps(report, sort_keys=True)})
        if not report_secret_hygiene["ok"]:
            secret_hygiene = _merge_secret_hygiene(secret_hygiene, report_secret_hygiene)
            report["checks"]["secret_hygiene"] = False
            report["manifest"]["secret_hygiene_finding_count"] = secret_hygiene["finding_count"]
            report["manifest"]["secret_hygiene_ok"] = False
            report["ok"] = _release_checks_ok(report["checks"])
        return report


def _release_smoke_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("ok") is True else 1


def _single_wheel(wheel_dir: Path) -> Path:
    wheels = sorted(wheel_dir.glob(f"{PACKAGE_NAME}-*.whl"))
    if len(wheels) != 1:
        raise AssertionError(f"expected one {PACKAGE_NAME} wheel, found {[wheel.name for wheel in wheels]}")
    return wheels[0]


def _release_checks_ok(checks: dict[str, Any]) -> bool:
    bool_checks_ok = all(value is True for value in checks.values() if isinstance(value, bool))
    eval_checks = checks.get("eval_checks")
    eval_summary_ok = isinstance(eval_checks, dict) and eval_checks.get("failed") == 0
    deployment_checks = checks.get("deployment_checks")
    deployment_summary_ok = isinstance(deployment_checks, dict) and deployment_checks.get("failed") == 0
    return bool_checks_ok and eval_summary_ok and deployment_summary_ok


def _run_packaged_deployment_check(
    console: Path,
    deployment_root: Path,
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    workspace_id = "release-smoke-workspace"
    owner_id = "release-smoke-owner"
    _run(
        [
            str(console),
            "--root",
            str(deployment_root),
            "workspace",
            "Release Smoke",
            "--workspace-id",
            workspace_id,
        ],
        cwd=cwd,
        env=env,
    )
    _run(
        [
            str(console),
            "--root",
            str(deployment_root),
            "add-member",
            workspace_id,
            owner_id,
            "--role",
            "owner",
        ],
        cwd=cwd,
        env=env,
    )
    _run(
        [
            str(console),
            "--root",
            str(deployment_root),
            "create-token",
            workspace_id,
            owner_id,
            "--name",
            "release-smoke",
            "--scope",
            "read",
            "--scope",
            "write",
            "--scope",
            "audit",
        ],
        cwd=cwd,
        env=env,
    )
    result = _run(
        [
            str(console),
            "--root",
            str(deployment_root),
            "deployment-check",
            "--require-api-token",
            "--fail-on-unready",
        ],
        cwd=cwd,
        env=env,
    )
    return json.loads(result.stdout)


def _release_secret_hygiene(outputs: dict[str, str]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for output_name, value in outputs.items():
        text = value or ""
        for kind, pattern in SECRET_SHAPED_PATTERNS.items():
            if pattern.search(text):
                findings.append({"output": output_name, "kind": kind})
    return {
        "ok": not findings,
        "finding_count": len(findings),
        "findings": findings,
    }


def _merge_secret_hygiene(*reports: dict[str, Any]) -> dict[str, Any]:
    findings = [finding for report in reports for finding in report.get("findings", [])]
    return {
        "ok": not findings,
        "finding_count": len(findings),
        "findings": findings,
    }


def _inspect_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        entry_points = archive.read(f"{PACKAGE_NAME}-{VERSION}.dist-info/entry_points.txt").decode()
    required = {
        "pageindex/config.yaml",
        "pageindex_enterprise/__main__.py",
        f"{PACKAGE_NAME}-{VERSION}.dist-info/METADATA",
    }
    missing = sorted(required - names)
    if missing:
        raise AssertionError(f"wheel missing files: {missing}")
    if "pageindex-enterprise = pageindex_enterprise.__main__:main" not in entry_points:
        raise AssertionError("wheel console entrypoint is missing")


def _artifact_manifest(
    wheel: Path,
    *,
    package_metadata: dict[str, str],
    build_environment: dict[str, str],
    source: dict[str, Any],
    dependencies: list[dict[str, Any]],
    dependency_policy: dict[str, Any],
    wheel_record: dict[str, Any],
    wheel_content: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package": {
            "name": "pageindex-enterprise-cleanroom",
            "version": VERSION,
            "license_declared": package_metadata["license_declared"],
            "summary": package_metadata["summary"],
        },
        "build_environment": build_environment,
        "source": source,
        "dependencies": dependencies,
        "dependency_policy": dependency_policy,
        "artifacts": [
            {
                "content": wheel_content,
                "filename": wheel.name,
                "record": wheel_record,
                "sha256": _sha256(wheel),
                "size_bytes": wheel.stat().st_size,
            }
        ],
    }


def _sbom_document(manifest: dict[str, Any]) -> dict[str, Any]:
    package = manifest["package"]
    artifact = manifest["artifacts"][0]
    root_spdx_id = "SPDXRef-Package-pageindex-enterprise-cleanroom"
    packages = [
        {
            "SPDXID": root_spdx_id,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": package["license_declared"],
            "name": package["name"],
            "versionInfo": package["version"],
            "checksums": [
                {
                    "algorithm": "SHA256",
                    "checksumValue": artifact["sha256"],
                }
            ],
        }
    ]
    relationships: list[dict[str, str]] = []
    for dependency in manifest["dependencies"]:
        dep_spdx_id = f"SPDXRef-Dependency-{_spdx_identifier(dependency['name'])}"
        packages.append(
            {
                "SPDXID": dep_spdx_id,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "name": dependency["name"],
                "versionInfo": _dependency_version_info(dependency),
            }
        )
        relationships.append(
            {
                "spdxElementId": root_spdx_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dep_spdx_id,
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{package['name']}-{package['version']}",
        "documentNamespace": (
            "https://pageindex.local/sbom/"
            f"{package['name']}-{package['version']}-{artifact['sha256']}"
        ),
        "creationInfo": {
            "creators": ["Tool: pageindex-enterprise release_smoke.py"],
            "created": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        },
        "packages": packages,
        "relationships": relationships,
    }


def _spdx_identifier(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9.-]", "-", value)
    return safe.strip(".-") or "package"


def _dependency_version_info(dependency: dict[str, Any]) -> str:
    specifier = dependency.get("specifier")
    if isinstance(specifier, str) and specifier.startswith("=="):
        return specifier.removeprefix("==")
    return "NOASSERTION"


def _wheel_package_metadata(wheel: Path) -> dict[str, str]:
    metadata_path = f"{PACKAGE_NAME}-{VERSION}.dist-info/METADATA"
    with zipfile.ZipFile(wheel) as archive:
        metadata = Parser().parsestr(archive.read(metadata_path).decode("utf-8"))
    return {
        "license_declared": _spdx_license_declared(metadata.get("License")),
        "name": metadata.get("Name", ""),
        "summary": metadata.get("Summary", ""),
        "version": metadata.get("Version", ""),
    }


def _spdx_license_declared(value: str | None) -> str:
    if value is None:
        return "NOASSERTION"
    normalized = value.strip()
    if not normalized or normalized.upper() == "UNKNOWN":
        return "NOASSERTION"
    return normalized


def _build_environment() -> dict[str, str]:
    return {
        "architecture": platform.machine(),
        "platform": platform.platform(),
        "python_executable": Path(sys.executable).name,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "system": platform.system(),
    }


def _build_environment_ok(environment: dict[str, str]) -> bool:
    required = {
        "architecture",
        "platform",
        "python_executable",
        "python_implementation",
        "python_version",
        "system",
    }
    return all(isinstance(environment.get(key), str) and bool(environment[key]) for key in required)


def _wheel_dependencies(wheel: Path) -> list[dict[str, Any]]:
    metadata_path = f"{PACKAGE_NAME}-{VERSION}.dist-info/METADATA"
    dependencies: list[dict[str, Any]] = []
    with zipfile.ZipFile(wheel) as archive:
        metadata = archive.read(metadata_path).decode("utf-8")
    for line in metadata.splitlines():
        if not line.startswith("Requires-Dist: "):
            continue
        requirement = line.removeprefix("Requires-Dist: ").strip()
        match = re.match(r"^([A-Za-z0-9_.-]+)(.*)$", requirement)
        name = match.group(1) if match else requirement
        rest = match.group(2).strip() if match else ""
        specifier = _requirement_specifier(rest)
        dependencies.append(
            {
                "name": name.lower().replace("_", "-"),
                "pinned": _is_exact_pin(specifier),
                "requirement": requirement,
                "specifier": specifier,
            }
        )
    return sorted(dependencies, key=lambda dep: dep["name"])


def _wheel_content_policy(wheel: Path) -> dict[str, Any]:
    blocked: list[dict[str, str]] = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            reason = _blocked_wheel_entry_reason(name)
            if reason is not None:
                blocked.append({"path": name, "reason": reason})
    return {
        "ok": not blocked,
        "blocked": blocked,
        "blocked_count": len(blocked),
    }


def _blocked_wheel_entry_reason(name: str) -> str | None:
    parts = name.split("/")
    basename = parts[-1]
    if any(part in {".git", ".mypy_cache", ".omx", ".pytest_cache", ".ruff_cache", "__pycache__"} for part in parts):
        return "local_state"
    if basename in {".DS_Store", ".env"}:
        return "local_state"
    lowered = basename.lower()
    for suffix in (".db", ".pem", ".pyo", ".pyc", ".sqlite"):
        if lowered.endswith(suffix):
            return "blocked_suffix"
    if lowered.endswith((".key", ".keyfile")):
        return "private_key_candidate"
    return None


def _wheel_record_integrity(wheel: Path) -> dict[str, Any]:
    record_path = f"{PACKAGE_NAME}-{VERSION}.dist-info/RECORD"
    malformed: list[dict[str, Any]] = []
    missing: list[str] = []
    mismatches: list[dict[str, Any]] = []
    unhashed_non_record: list[str] = []
    entries = 0
    hashed_entries = 0
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        if record_path not in names:
            return {
                "ok": False,
                "entries": 0,
                "hashed_entries": 0,
                "missing": [record_path],
                "mismatches": [],
                "unhashed_non_record": [],
            }
        rows = csv.reader(io.StringIO(archive.read(record_path).decode("utf-8")))
        for row in rows:
            entries += 1
            if len(row) != 3:
                malformed.append({"row": entries, "columns": len(row)})
                continue
            path, hash_field, size_field = row
            if path not in names:
                missing.append(path)
                continue
            data = archive.read(path)
            if hash_field:
                hashed_entries += 1
                algorithm, separator, expected = hash_field.partition("=")
                actual = _sha256_record_digest(data)
                if algorithm != "sha256" or separator != "=":
                    mismatches.append({"path": path, "reason": "unsupported_hash", "algorithm": algorithm})
                elif actual != expected:
                    mismatches.append({"path": path, "reason": "hash_mismatch"})
            elif path != record_path:
                unhashed_non_record.append(path)
            if size_field:
                try:
                    expected_size = int(size_field)
                except ValueError:
                    mismatches.append({"path": path, "reason": "invalid_size"})
                else:
                    if len(data) != expected_size:
                        mismatches.append({"path": path, "reason": "size_mismatch"})
            elif path != record_path:
                mismatches.append({"path": path, "reason": "missing_size"})
    return {
        "ok": not malformed and not missing and not mismatches and not unhashed_non_record,
        "entries": entries,
        "hashed_entries": hashed_entries,
        "malformed": malformed,
        "missing": missing,
        "mismatches": mismatches,
        "unhashed_non_record": unhashed_non_record,
    }


def _sha256_record_digest(data: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")


def _dependency_policy(dependencies: list[dict[str, Any]]) -> dict[str, Any]:
    unpinned = [str(dep["name"]) for dep in dependencies if not dep.get("pinned")]
    return {
        "direct_dependencies_pinned": bool(dependencies) and not unpinned,
        "unpinned": unpinned,
    }


def _is_exact_pin(specifier: str | None) -> bool:
    return bool(specifier and re.fullmatch(r"==[^,;\\s]+", specifier))


def _requirement_specifier(rest: str) -> str | None:
    if not rest:
        return None
    marker_index = rest.find(";")
    if marker_index >= 0:
        rest = rest[:marker_index].strip()
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()
    return rest or None


def _source_metadata(repo_root: Path) -> dict[str, Any]:
    dirty_paths = _git_status_entries(repo_root)
    return {
        "branch": _git_output(repo_root, "branch", "--show-current"),
        "commit": _git_output(repo_root, "rev-parse", "HEAD"),
        "dirty": bool(dirty_paths),
        "dirty_count": len(dirty_paths),
        "dirty_paths": dirty_paths[:SOURCE_DIRTY_PATH_LIMIT],
        "dirty_paths_truncated": len(dirty_paths) > SOURCE_DIRTY_PATH_LIMIT,
        "remote": _git_output(repo_root, "config", "--get", "remote.origin.url"),
        "upstream": _git_output(repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"),
    }


def _git_status_entries(repo_root: Path) -> list[str]:
    output = _git_output(repo_root, "status", "--short")
    if output is None:
        return []
    return [line for line in output.splitlines() if line.strip()]


def _git_output(repo_root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
