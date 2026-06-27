from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from .llm import validate_openai_compatible_config
from .store import AUDIT_SINK_FORMATS, EnterpriseStore, WORKSPACE_ADMIN_ROLES, _decode_api_token_scopes, _is_expired


EXPECTED_TABLES = {
    "workspaces",
    "workspace_members",
    "workspace_invitations",
    "workspace_groups",
    "workspace_group_members",
    "api_tokens",
    "api_token_policies",
    "workspace_quota_policies",
    "workspace_provider_configs",
    "workspace_audit_jsonl_sinks",
    "audit_retention_policies",
    "query_retention_policies",
    "audit_events",
    "folders",
    "folder_access_grants",
    "folder_group_access_grants",
    "documents",
    "document_access_grants",
    "document_group_access_grants",
    "document_share_links",
    "document_pages",
    "document_versions",
    "query_source_sets",
    "query_source_set_documents",
    "query_source_set_share_links",
    "query_runs",
    "conversations",
    "conversation_share_links",
    "conversation_messages",
    "evidence",
    "citations",
    "virtual_nodes",
    "virtual_node_docs",
}


def run_deployment_check(
    root: str | Path,
    *,
    require_api_token: bool = False,
    check_provider: bool = False,
    require_provider_api_key: bool = False,
    require_audit_sink: bool = False,
    require_audit_sink_format: str | None = None,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    required_audit_sink_format = _normalize_required_audit_sink_format(require_audit_sink_format)
    root_writable = _root_writable_check(root_path)
    if not root_writable["ok"]:
        return _deployment_report(
            root_path,
            {
                "root_writable": root_writable,
                "schema": _check(False, error="store was not opened because root is not writable"),
                "workspace_owner": _check(False, workspace_count=0, owner_count=0, skipped=True),
                "audit_integrity": _check(False, workspace_count=0, skipped=True),
                "audit_sink_delivery": _unavailable_audit_sink_delivery_check(
                    require_audit_sink,
                    required_format=required_audit_sink_format,
                    reason="store was not opened because root is not writable",
                ),
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
                "audit_sink_delivery": _unavailable_audit_sink_delivery_check(
                    require_audit_sink,
                    required_format=required_audit_sink_format,
                    reason="store was not opened",
                ),
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
            "audit_sink_delivery": _audit_sink_delivery_check(
                store,
                require_audit_sink=require_audit_sink,
                required_format=required_audit_sink_format,
            ),
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


def _normalize_required_audit_sink_format(format: str | None) -> str | None:
    if format is None:
        return None
    if not isinstance(format, str):
        raise ValueError("require_audit_sink_format must be a string")
    normalized = format.strip().casefold()
    if not normalized:
        return None
    if normalized not in AUDIT_SINK_FORMATS:
        raise ValueError("require_audit_sink_format must be jsonl or siem-jsonl")
    return normalized


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
    return _check(
        not missing,
        table_count=len(tables),
        expected_table_count=len(EXPECTED_TABLES),
        missing_tables=missing,
    )


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
    admin_by_workspace = _admin_actor_by_workspace(store)
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


def _unavailable_audit_sink_delivery_check(
    require_audit_sink: bool,
    *,
    required_format: str | None = None,
    reason: str,
) -> dict[str, Any]:
    required = require_audit_sink or required_format is not None
    return _check(
        not required,
        required=required,
        required_format=required_format,
        workspace_count=0,
        configured_count=0,
        enabled_count=0,
        healthy_count=0,
        delivered_count=0,
        disabled_count=0,
        unconfigured_count=0,
        matching_format_count=0,
        skipped=not required,
        reason=reason,
    )


def _audit_sink_delivery_check(
    store: EnterpriseStore,
    *,
    require_audit_sink: bool = False,
    required_format: str | None = None,
) -> dict[str, Any]:
    required = require_audit_sink or required_format is not None
    workspace_ids = [row["id"] for row in store.conn.execute("SELECT id FROM workspaces ORDER BY id")]
    if not workspace_ids:
        return _check(
            not required,
            required=required,
            required_format=required_format,
            workspace_count=0,
            configured_count=0,
            enabled_count=0,
            healthy_count=0,
            delivered_count=0,
            disabled_count=0,
            unconfigured_count=0,
            matching_format_count=0,
            skipped=not required,
            reason="no workspaces",
        )
    admin_by_workspace = _admin_actor_by_workspace(store)
    reports: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    configured_count = 0
    enabled_count = 0
    healthy_count = 0
    delivered_count = 0
    disabled_count = 0
    matching_format_count = 0
    format_counts = {"jsonl": 0, "siem-jsonl": 0}
    unconfigured: list[str] = []
    missing_operators: list[str] = []
    for workspace_id in workspace_ids:
        user_id = admin_by_workspace.get(workspace_id)
        if not user_id:
            missing_operators.append(workspace_id)
            continue
        config = store.get_workspace_audit_jsonl_sink_config(workspace_id, user_id)
        if not config.get("configured"):
            unconfigured.append(workspace_id)
            continue
        configured_count += 1
        sink_format = str(config.get("format") or "jsonl")
        if sink_format in format_counts:
            format_counts[sink_format] += 1
        format_ok = required_format is None or sink_format == required_format
        if format_ok:
            matching_format_count += 1
        if not config.get("enabled"):
            disabled_count += 1
            if required:
                failures.append(
                    {
                        "workspace_id": workspace_id,
                        "reason": "disabled",
                        "relative_path": config.get("relative_path"),
                        "format": sink_format,
                        "expected_format": required_format,
                    }
                )
            reports.append(
                {
                    "workspace_id": workspace_id,
                    "configured": True,
                    "enabled": False,
                    "format": sink_format,
                    "format_ok": format_ok,
                    "relative_path": config.get("relative_path"),
                    "reason": "disabled",
                }
            )
            continue
        enabled_count += 1
        report = store.get_workspace_audit_jsonl_sink_status(workspace_id, user_id)
        delivered = (
            bool(report.get("sink_exists"))
            and int(report.get("line_count") or 0) > 0
            and report.get("last_line_valid") is True
        )
        if report.get("ok"):
            healthy_count += 1
            if delivered:
                delivered_count += 1
            else:
                failures.append(
                    {
                        "workspace_id": workspace_id,
                        "reason": "no_delivered_events",
                        "relative_path": report.get("relative_path"),
                        "format": report.get("format"),
                        "sink_exists": report.get("sink_exists"),
                        "line_count": report.get("line_count"),
                        "last_line_valid": report.get("last_line_valid"),
                    }
                )
            if not format_ok:
                failures.append(
                    {
                        "workspace_id": workspace_id,
                        "reason": "format_mismatch",
                        "relative_path": report.get("relative_path"),
                        "format": report.get("format"),
                        "expected_format": required_format,
                    }
                )
        else:
            failures.append(
                {
                    "workspace_id": workspace_id,
                    "reason": report.get("reason"),
                    "relative_path": report.get("relative_path"),
                    "format": report.get("format"),
                    "checks": report.get("checks"),
                }
            )
        reports.append(
            {
                "workspace_id": workspace_id,
                "configured": True,
                "enabled": True,
                "ok": bool(report.get("ok")),
                "format": report.get("format"),
                "format_ok": format_ok,
                "relative_path": report.get("relative_path"),
                "reason": report.get("reason"),
                "checks": report.get("checks"),
                "sink_exists": report.get("sink_exists"),
                "line_count": report.get("line_count"),
                "last_line_valid": report.get("last_line_valid"),
                "last_event": report.get("last_event"),
                "delivered": delivered,
            }
        )
    if missing_operators:
        failures.extend(
            {"workspace_id": workspace_id, "reason": "missing owner/admin member"}
            for workspace_id in missing_operators
        )
    if required:
        failures.extend(
            {"workspace_id": workspace_id, "reason": "not_configured"}
            for workspace_id in unconfigured
        )
    return _check(
        not failures,
        required=required,
        required_format=required_format,
        workspace_count=len(workspace_ids),
        configured_count=configured_count,
        enabled_count=enabled_count,
        healthy_count=healthy_count,
        delivered_count=delivered_count,
        disabled_count=disabled_count,
        unconfigured_count=len(unconfigured),
        matching_format_count=matching_format_count,
        format_counts=format_counts,
        skipped=configured_count == 0 and not required,
        sink_reports=reports[:10],
        unconfigured_workspace_ids=unconfigured[:10],
        failing_workspaces=failures[:10],
    )


def _admin_actor_by_workspace(store: EnterpriseStore) -> dict[str, str]:
    admin_roles = tuple(WORKSPACE_ADMIN_ROLES)
    placeholders = ", ".join("?" for _ in admin_roles)
    rows = store.conn.execute(
        f"""
        SELECT workspace_id, user_id
        FROM workspace_members
        WHERE role IN ({placeholders})
        ORDER BY workspace_id, CASE role WHEN 'owner' THEN 0 ELSE 1 END, user_id
        """,
        admin_roles,
    ).fetchall()
    admin_by_workspace: dict[str, str] = {}
    for row in rows:
        admin_by_workspace.setdefault(row["workspace_id"], row["user_id"])
    return admin_by_workspace


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
