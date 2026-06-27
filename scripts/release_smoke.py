from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


PACKAGE_NAME = "pageindex_enterprise_cleanroom"
VERSION = "0.1.0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and smoke-test the PageIndex enterprise wheel.")
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = run_release_smoke(Path(args.repo_root))
    print(json.dumps(report, indent=2, sort_keys=True))


def run_release_smoke(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="pageindex-release-smoke-") as tmp:
        tmp_path = Path(tmp)
        wheel_dir = tmp_path / "wheels"
        install_dir = tmp_path / "install"
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
        _inspect_wheel(wheel)
        return {
            "ok": eval_report.get("ok") is True,
            "wheel": wheel.name,
            "checks": {
                "wheel_built": wheel.name == f"{PACKAGE_NAME}-{VERSION}-py3-none-any.whl",
                "console_script": "usage:" in help_result.stdout and "eval" in help_result.stdout,
                "eval_command": eval_report.get("ok") is True,
                "eval_checks": eval_report.get("summary", {}),
            },
        }


def _single_wheel(wheel_dir: Path) -> Path:
    wheels = sorted(wheel_dir.glob(f"{PACKAGE_NAME}-*.whl"))
    if len(wheels) != 1:
        raise AssertionError(f"expected one {PACKAGE_NAME} wheel, found {[wheel.name for wheel in wheels]}")
    return wheels[0]


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
