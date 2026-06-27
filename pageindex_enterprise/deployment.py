from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from .llm import validate_openai_compatible_config
from .store import EnterpriseStore, WORKSPACE_ADMIN_ROLES, _decode_api_token_scopes, _is_expired


EXPECTED_TABLES = {
    "workspaces",
    "workspace_members",
    "api_tokens",
    "workspace_provider_configs",
    "documents",
    "document_pages",
    "query_runs",
    "evidence",
    "citations",
    "audit_events",
}


def run_deployment_check(
    root: str | Path,
    *,
    require_api_token: bool = False,
    check_provider: bool = False,
    require_provider_api_key: bool = False,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    root_writable = _root_writable_check(root_path)
    if not root_writable["ok"]:
        return _deployment_report(
            root_path,
            {
                "root_writable": root_writable,
                "schema": _check(False, error="store was not opened because root is not writable"),
                "workspace_owner": _check(False, workspace_count=0, owner_count=0, skipped=True),
                "audit_integrity": _check(False, workspace_count=0, skipped=True),
                "strict_http": _strict_http_check(require_api_token),
                "active_api_token": _check(False, active_token_count=0, skipped=True),
                "provider_config": _provider_config_check(
                    check_provider=check_provider,
                    require_provider_api_key=require_provider_api_key,
                ),
            },
        )
    try:
        store = EnterpriseStore(root_path)
    except Exception as exc:
        return _deployment_report(
            root_path,
            {
                "root_writable": root_writable,
                "schema": _check(False, error=str(exc)),
                "workspace_owner": _check(False, workspace_count=0, owner_count=0, skipped=True),
                "audit_integrity": _check(False, workspace_count=0, skipped=True),
                "strict_http": _strict_http_check(require_api_token),
                "active_api_token": _check(False, active_token_count=0, skipped=True),
                "provider_config": _provider_config_check(
                    check_provider=check_provider,
                    require_provider_api_key=require_provider_api_key,
                ),
            },
        )
    try:
        checks = {
            "root_writable": root_writable,
            "schema": _schema_check(store),
            "workspace_owner": _workspace_owner_check(store),
            "audit_integrity": _audit_integrity_check(store),
            "strict_http": _strict_http_check(require_api_token),
            "active_api_token": _active_api_token_check(store),
            "provider_config": _provider_config_check(
                check_provider=check_provider,
                require_provider_api_key=require_provider_api_key,
            ),
        }
    finally:
        store.close()
    return _deployment_report(root_path, checks)


def _deployment_report(root_path: Path, checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for check in checks.values() if check["ok"])
    total = len(checks)
    return {
        "ok": passed == total,
        "root": str(root_path),
        "checks": checks,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
        },
    }


def _check(ok: bool, **details: Any) -> dict[str, Any]:
    return {"ok": bool(ok), **details}


def _root_writable_check(root: Path) -> dict[str, Any]:
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / f".deployment-check-{uuid.uuid4().hex}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return _check(False, path=str(root), error=str(exc))
    return _check(True, path=str(root))


def _schema_check(store: EnterpriseStore) -> dict[str, Any]:
    rows = store.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    tables = {row["name"] for row in rows}
    missing = sorted(EXPECTED_TABLES - tables)
    return _check(not missing, table_count=len(tables), missing_tables=missing)


def _workspace_owner_check(store: EnterpriseStore) -> dict[str, Any]:
    workspace_count = store.conn.execute("SELECT COUNT(*) AS count FROM workspaces").fetchone()["count"]
    owner_count = store.conn.execute(
        "SELECT COUNT(*) AS count FROM workspace_members WHERE role = 'owner'"
    ).fetchone()["count"]
    return _check(
        workspace_count > 0 and owner_count > 0,
        workspace_count=workspace_count,
        owner_count=owner_count,
    )


def _audit_integrity_check(store: EnterpriseStore) -> dict[str, Any]:
    workspaces = [row["id"] for row in store.conn.execute("SELECT id FROM workspaces ORDER BY id")]
    if not workspaces:
        return _check(True, workspace_count=0, checked=0, legacy=0, skipped=True)
    admin_roles = tuple(WORKSPACE_ADMIN_ROLES)
    placeholders = ", ".join("?" for _ in admin_roles)
    admin_rows = store.conn.execute(
        f"""
        SELECT workspace_id, user_id
        FROM workspace_members
        WHERE role IN ({placeholders})
        ORDER BY workspace_id, CASE role WHEN 'owner' THEN 0 ELSE 1 END, user_id
        """,
        admin_roles,
    ).fetchall()
    admin_by_workspace: dict[str, str] = {}
    for row in admin_rows:
        admin_by_workspace.setdefault(row["workspace_id"], row["user_id"])
    failures: list[dict[str, Any]] = []
    checked = 0
    legacy = 0
    for workspace_id in workspaces:
        user_id = admin_by_workspace.get(workspace_id)
        if not user_id:
            failures.append({"workspace_id": workspace_id, "error": "missing owner/admin member"})
            continue
        report = store.verify_audit_integrity(workspace_id, user_id)
        checked += int(report.get("checked", 0))
        legacy += int(report.get("legacy", 0))
        if not report.get("ok"):
            failures.append(
                {
                    "workspace_id": workspace_id,
                    "failure_count": report.get("failure_count", 0),
                    "failures": report.get("failures", [])[:3],
                }
            )
    return _check(
        not failures,
        workspace_count=len(workspaces),
        checked=checked,
        legacy=legacy,
        failing_workspaces=failures,
    )


def _strict_http_check(require_api_token: bool) -> dict[str, Any]:
    return _check(
        require_api_token,
        require_api_token=require_api_token,
        message=(
            "strict Bearer-token mode is enabled"
            if require_api_token
            else "production deployments should run serve --require-api-token"
        ),
    )


def _active_api_token_check(store: EnterpriseStore) -> dict[str, Any]:
    rows = store.conn.execute(
        "SELECT workspace_id, user_id, expires_at, scopes_json FROM api_tokens"
    ).fetchall()
    active_count = 0
    for row in rows:
        scopes = _decode_api_token_scopes(row["scopes_json"])
        if (
            scopes
            and not _is_expired(row["expires_at"])
            and store.user_can_access_workspace(row["workspace_id"], row["user_id"])
        ):
            active_count += 1
    return _check(active_count > 0, active_token_count=active_count)


def _provider_config_check(*, check_provider: bool, require_provider_api_key: bool) -> dict[str, Any]:
    provider_config_present = bool(os.environ.get("PAGEINDEX_LLM_BASE_URL", "").strip())
    if not check_provider and not provider_config_present:
        return _check(True, skipped=True, reason="provider config not requested")
    try:
        config = validate_openai_compatible_config(require_api_key=require_provider_api_key)
    except ValueError as exc:
        return _check(False, error=str(exc), api_key_configured=bool(os.environ.get("PAGEINDEX_LLM_API_KEY")))
    return _check(True, **config)
