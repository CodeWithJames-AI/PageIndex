from __future__ import annotations

import csv
import hashlib
import html
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .llm import validate_openai_compatible_config


WORKSPACE_WRITE_ROLES = {"owner", "admin", "member"}
WORKSPACE_ADMIN_ROLES = {"owner", "admin"}
WORKSPACE_ROLES = {"owner", "admin", "member", "viewer"}
WORKSPACE_INVITATION_ROLES = {"admin", "member", "viewer"}
WORKSPACE_ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}
DOCUMENT_ACCESS_MODES = {"workspace", "restricted"}
DOCUMENT_ACCESS_GRANT_ROLES = {"read", "write"}
API_TOKEN_SCOPES = ("read", "write", "audit")
MAX_CONVERSATION_MESSAGE_CHARS = 4000
MAX_CONVERSATION_TITLE_CHARS = 72
DEFAULT_CONVERSATION_TITLE = "New conversation"
MAX_SHARE_PASSWORD_CHARS = 256
MAX_LEGAL_HOLD_REASON_CHARS = 500
SHARE_PASSWORD_HASH_ITERATIONS = 120_000
CHAT_TRACE_QUERY = "[conversation message redacted]"
QUESTION_SUGGESTION_STOPWORDS = {
    "about",
    "after",
    "also",
    "analysis",
    "because",
    "between",
    "chapter",
    "content",
    "document",
    "documents",
    "during",
    "evidence",
    "from",
    "have",
    "into",
    "page",
    "pages",
    "report",
    "section",
    "their",
    "there",
    "these",
    "this",
    "through",
    "using",
    "what",
    "when",
    "where",
    "which",
    "with",
}
WORKSPACE_EXPORT_FORMAT = "pageindex.workspace-export.v1"
WORKSPACE_EXPORT_TABLES = (
    "workspace",
    "workspace_members",
    "workspace_invitations",
    "workspace_groups",
    "workspace_group_members",
    "folders",
    "folder_access_grants",
    "folder_group_access_grants",
    "documents",
    "document_access_grants",
    "document_group_access_grants",
    "query_source_sets",
    "query_source_set_documents",
    "document_pages",
    "document_versions",
    "conversations",
    "conversation_messages",
    "query_runs",
    "evidence",
    "citations",
    "virtual_nodes",
    "api_token_policy",
    "query_retention_policy",
    "audit_retention_policy",
    "workspace_quota_policy",
    "provider_config",
    "audit_events",
)
WORKSPACE_EXPORT_OPTIONAL_TABLES = ("query_source_sets", "query_source_set_documents")
WORKSPACE_IMPORT_INSERT_ORDER = (
    "workspace",
    "workspace_members",
    "workspace_invitations",
    "workspace_groups",
    "workspace_group_members",
    "folders",
    "documents",
    "query_source_sets",
    "query_source_set_documents",
    "folder_access_grants",
    "folder_group_access_grants",
    "document_access_grants",
    "document_group_access_grants",
    "document_pages",
    "document_versions",
    "query_runs",
    "evidence",
    "citations",
    "conversations",
    "conversation_messages",
    "virtual_nodes",
    "api_token_policy",
    "query_retention_policy",
    "audit_retention_policy",
    "workspace_quota_policy",
    "provider_config",
    "audit_events",
)
WORKSPACE_IMPORT_DB_TABLES = {
    "workspace": "workspaces",
    "api_token_policy": "api_token_policies",
    "query_retention_policy": "query_retention_policies",
    "audit_retention_policy": "audit_retention_policies",
    "workspace_quota_policy": "workspace_quota_policies",
    "provider_config": "workspace_provider_configs",
}
WORKSPACE_EXPORT_OMITTED_TABLES = (
    "api_tokens",
    "document_share_links",
    "conversation_share_links",
    "query_source_set_share_links",
)
WORKSPACE_EXPORT_REQUIRED_OMITTED_POLICIES = ("api_tokens", "document filesystem paths")
WORKSPACE_EXPORT_OMITTED_POLICIES = (*WORKSPACE_EXPORT_REQUIRED_OMITTED_POLICIES, "public share link secrets")
_UNSET = object()
_AUDIT_SINK_SECRET_VALUE = re.compile(r"(pit_[A-Za-z0-9_-]+|Bearer\s+\S+|sk-[A-Za-z0-9_-]+)", re.IGNORECASE)
_EMAIL_ADDRESS = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_ENV_VAR_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_ABSOLUTE_SOURCE_PATH = re.compile(
    r"(^|[\s:\"'])(/(?:Users|home|tmp|private|var|Volumes|opt|etc)/[^\s\"']+|[A-Za-z]:\\[^\s\"']+)"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_expires_at(expires_at: str | None) -> str | None:
    if expires_at is None:
        return None
    expires_at = expires_at.strip()
    if not expires_at:
        return None
    parsed = _parse_iso_datetime(expires_at)
    return parsed.isoformat()


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        return _parse_iso_datetime(expires_at) <= _now_dt()
    except ValueError:
        return True


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def expires_at_from_days(days: int | None) -> str | None:
    if days is None:
        return None
    if days <= 0:
        raise ValueError("expires-in-days must be positive")
    return (_now_dt() + timedelta(days=days)).isoformat()


def _normalize_policy_days(days: int | None, name: str) -> int | None:
    if days is None:
        return None
    if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return days


def _normalize_share_max_views(max_views: int | None) -> int | None:
    return _normalize_policy_days(max_views, "max_views")


def _normalize_share_password(password: str | None) -> str | None:
    if password is None:
        return None
    if not isinstance(password, str):
        raise ValueError("password must be a string")
    normalized = password.strip()
    if not normalized:
        return None
    if len(normalized) > MAX_SHARE_PASSWORD_CHARS:
        raise ValueError(f"password must be {MAX_SHARE_PASSWORD_CHARS} characters or fewer")
    return normalized


def _share_password_digest(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        SHARE_PASSWORD_HASH_ITERATIONS,
    ).hex()


def _share_password_fields(password: str | None) -> tuple[str | None, str | None]:
    normalized = _normalize_share_password(password)
    if normalized is None:
        return None, None
    salt = secrets.token_hex(16)
    return salt, _share_password_digest(normalized, salt)


def _share_password_matches(password: str | None, salt: str | None, expected_hash: str | None) -> bool:
    if not expected_hash:
        return True
    normalized = _normalize_share_password(password)
    if normalized is None or not salt:
        return False
    return hmac.compare_digest(_share_password_digest(normalized, salt), expected_hash)


def _normalize_quota_limit(limit: int | None, name: str) -> int | None:
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"{name} must be a positive integer or null")
    return limit


def _normalize_source_set_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("Source set name is required.")
    if len(normalized) > 120:
        raise ValueError("Source set name must be 120 characters or fewer.")
    return normalized


def _normalize_source_set_description(description: str | None) -> str:
    if description is None:
        return ""
    normalized = " ".join(description.split())
    if len(normalized) > 500:
        raise ValueError("Source set description must be 500 characters or fewer.")
    return normalized


def _optional_source_set_id(source_set_id: str | None) -> str | None:
    if source_set_id is None:
        return None
    if not isinstance(source_set_id, str):
        raise ValueError("source_set_id must be a string")
    return source_set_id.strip() or None


def _optional_folder_id(folder_id: str | None) -> str | None:
    if folder_id is None:
        return None
    if not isinstance(folder_id, str):
        raise ValueError("folder_id must be a string")
    return folder_id.strip() or None


def _normalize_source_set_doc_ids(doc_ids: list[str] | None) -> list[str]:
    if not doc_ids:
        raise ValueError("At least one document id is required.")
    normalized: list[str] = []
    seen: set[str] = set()
    for doc_id in doc_ids:
        if not isinstance(doc_id, str):
            raise ValueError("Document ids must be strings.")
        doc_id = doc_id.strip()
        if not doc_id:
            continue
        if doc_id not in seen:
            normalized.append(doc_id)
            seen.add(doc_id)
    if not normalized:
        raise ValueError("At least one document id is required.")
    return normalized


def _normalize_legal_hold_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    if not isinstance(reason, str):
        raise ValueError("legal_hold_reason must be a string")
    normalized = " ".join(reason.split())
    if not normalized:
        return None
    if len(normalized) > MAX_LEGAL_HOLD_REASON_CHARS:
        raise ValueError(f"legal_hold_reason must be {MAX_LEGAL_HOLD_REASON_CHARS} characters or fewer")
    return normalized


def _normalize_provider_timeout(timeout_seconds: float | None) -> float | None:
    if timeout_seconds is None:
        return None
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    return float(timeout_seconds)


def _normalize_provider_env_var(api_key_env_var: str | None) -> str | None:
    if api_key_env_var is None:
        return None
    api_key_env_var = api_key_env_var.strip()
    if not api_key_env_var:
        return None
    if not _ENV_VAR_NAME.fullmatch(api_key_env_var):
        raise ValueError("api_key_env_var must be an uppercase environment variable name")
    return api_key_env_var


def _rotation_metadata(created_at: str, rotation_due_in_days: int | None) -> dict[str, Any]:
    if rotation_due_in_days is None:
        return {"rotation_due_at": None, "rotation_due": False}
    try:
        due_at = _parse_iso_datetime(created_at) + timedelta(days=rotation_due_in_days)
    except ValueError:
        return {"rotation_due_at": None, "rotation_due": True}
    return {
        "rotation_due_at": due_at.isoformat(),
        "rotation_due": due_at <= _now_dt(),
    }


def _normalize_datetime_filter(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return _parse_iso_datetime(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 datetime") from exc


def _normalize_api_token_scopes(scopes: list[str] | None) -> list[str]:
    if scopes is None:
        return list(API_TOKEN_SCOPES)
    normalized = {scope.strip().casefold() for scope in scopes if scope.strip()}
    if not normalized:
        raise ValueError("At least one api token scope is required.")
    unsupported = sorted(normalized - set(API_TOKEN_SCOPES))
    if unsupported:
        raise ValueError(f"Unsupported api token scope: {unsupported[0]}")
    return [scope for scope in API_TOKEN_SCOPES if scope in normalized]


def _normalize_workspace_role(role: str | None, *, invitation: bool = False) -> str:
    normalized = (role or "member").strip().casefold() or "member"
    allowed = WORKSPACE_INVITATION_ROLES if invitation else WORKSPACE_ROLES
    if normalized not in allowed:
        raise ValueError(f"Unsupported workspace role: {normalized}")
    return normalized


def _normalize_invitation_email(email: str) -> str:
    normalized = email.strip().casefold()
    if not normalized or "@" not in normalized:
        raise ValueError("Invitation email is required.")
    return normalized


def _normalize_document_access_mode(mode: str | None) -> str:
    normalized = (mode or "workspace").strip().casefold() or "workspace"
    if normalized not in DOCUMENT_ACCESS_MODES:
        raise ValueError(f"Unsupported document access mode: {normalized}")
    return normalized


def _normalize_document_access_role(role: str | None) -> str:
    normalized = (role or "read").strip().casefold() or "read"
    if normalized not in DOCUMENT_ACCESS_GRANT_ROLES:
        raise ValueError(f"Unsupported document access role: {normalized}")
    return normalized


def _decode_api_token_scopes(scopes_json: str | None) -> list[str] | None:
    if not scopes_json:
        return list(API_TOKEN_SCOPES)
    try:
        decoded = json.loads(scopes_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, list) or not all(isinstance(scope, str) for scope in decoded):
        return None
    try:
        return _normalize_api_token_scopes(decoded)
    except ValueError:
        return None


def _api_token_scopes_for_role(role: str | None) -> list[str]:
    if role in WORKSPACE_ADMIN_ROLES:
        return list(API_TOKEN_SCOPES)
    if role in WORKSPACE_WRITE_ROLES:
        return ["read", "write"]
    if role == "viewer":
        return ["read"]
    return []


def _cap_api_token_scopes_to_role(scopes: list[str], role: str | None) -> list[str]:
    allowed = _api_token_scopes_for_role(role)
    return [scope for scope in scopes if scope in allowed]


def _token_owner_user_id(actor_user_id: str, token_owner_user_id: str | None) -> str:
    owner = actor_user_id if token_owner_user_id is None else token_owner_user_id.strip()
    if not owner:
        raise ValueError("Token owner user id is required.")
    if owner != actor_user_id:
        raise PermissionError("cross-user token management is not supported")
    return owner


def _audit_sink_path(root: Path) -> Path | None:
    raw = os.environ.get("PAGEINDEX_AUDIT_SINK_JSONL", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        root = root.resolve()
        path = (root / path).resolve()
        if not _path_is_relative_to(path, root):
            return None
        return path
    return path.resolve()


def _normalize_audit_sink_relative_path(relative_path: Any) -> str:
    if not isinstance(relative_path, str):
        raise ValueError("audit sink path must be a string")
    raw = relative_path.strip()
    if not raw:
        raise ValueError("audit sink path is required")
    path = Path(raw)
    if path.is_absolute() or raw.startswith("~"):
        raise ValueError("audit sink path must be relative")
    if path.suffix.casefold() != ".jsonl":
        raise ValueError("audit sink path must end in .jsonl")
    probe_root = Path("/__pageindex_workspace_root__")
    resolved = (probe_root / path).resolve()
    if not _path_is_relative_to(resolved, probe_root):
        raise ValueError("audit sink path must stay inside the workspace root")
    return resolved.relative_to(probe_root).as_posix()


def _workspace_audit_sink_path(root: Path, relative_path: str) -> Path | None:
    try:
        normalized = _normalize_audit_sink_relative_path(relative_path)
    except ValueError:
        return None
    root = root.resolve()
    path = (root / normalized).resolve()
    if not _path_is_relative_to(path, root):
        return None
    return path


def _redact_audit_sink_event(event: dict[str, Any]) -> dict[str, Any]:
    return _redact_audit_sink_mapping(event)


def _rows(rows: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _audit_integrity_hash(
    *,
    event_id: str,
    workspace_id: str | None,
    user_id: str,
    action: str,
    target_type: str,
    target_id: str | None,
    details_json: str,
    created_at: str,
    previous_integrity_hash: str | None,
) -> str:
    payload = {
        "action": action,
        "created_at": created_at,
        "details": json.loads(details_json),
        "id": event_id,
        "previous_integrity_hash": previous_integrity_hash,
        "target_id": target_id,
        "target_type": target_type,
        "user_id": user_id,
        "workspace_id": workspace_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _workspace_audit_export_rows(conn: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM audit_events
        WHERE workspace_id = ?
        ORDER BY created_at, id
        """,
        (workspace_id,),
    )
    events = []
    redacted_chain = False
    for row in rows:
        event = dict(row)
        details = json.loads(event.pop("details_json"))
        event["details"] = details
        redacted = _redact_audit_sink_event(event)
        # Redacted payloads cannot carry the source row hash; mark the rest of the exported chain as legacy.
        if redacted_chain or redacted.get("details") != details:
            redacted_chain = True
            redacted["previous_integrity_hash"] = None
            redacted["integrity_hash"] = None
        events.append(redacted)
    return events


def validate_workspace_import_bundle(bundle_path: str | Path) -> dict[str, Any]:
    """Validate a workspace export bundle without mutating any store state."""
    path = Path(bundle_path).expanduser()
    errors: list[str] = []
    warnings: list[str] = []
    table_counts: dict[str, int] = {}
    manifest_tables: dict[str, int] = {}
    manifest_checksums: dict[str, str] = {}
    manifest: dict[str, Any] = {}

    def report() -> dict[str, Any]:
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "format": manifest.get("format"),
            "workspace_id": manifest.get("workspace_id"),
            "table_counts": table_counts,
            "manifest_tables": manifest_tables,
            "manifest_checksums": manifest_checksums,
            "artifact": path.name,
        }

    if not path.exists():
        errors.append(f"bundle not found: {path}")
        return report()
    if not path.is_file():
        errors.append(f"bundle is not a file: {path}")
        return report()

    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        errors.append("bundle must be a valid zip file")
        return report()

    with archive:
        names = set(archive.namelist())
        for name in names:
            if name.startswith("/") or ".." in Path(name).parts:
                errors.append(f"archive entry has unsafe path: {name}")

        if "manifest.json" not in names:
            errors.append("manifest.json is required")
            return report()

        manifest = _read_workspace_import_manifest(archive, errors)
        if not isinstance(manifest, dict):
            return report()

        if manifest.get("format") != WORKSPACE_EXPORT_FORMAT:
            errors.append(f"unsupported workspace export format: {manifest.get('format')!r}")
        if not isinstance(manifest.get("workspace_id"), str) or not manifest.get("workspace_id", "").strip():
            errors.append("manifest workspace_id must be a non-empty string")

        tables = manifest.get("tables")
        if not isinstance(tables, dict):
            errors.append("manifest tables must be an object")
            tables = {}
        for table, count in tables.items():
            if isinstance(table, str) and isinstance(count, int) and count >= 0:
                manifest_tables[table] = count
            else:
                errors.append(f"manifest table count must be a non-negative integer: {table}")

        omitted = manifest.get("omitted")
        if not isinstance(omitted, list) or not all(isinstance(item, str) for item in omitted):
            errors.append("manifest omitted must be a list of strings")
            omitted_values: set[str] = set()
        else:
            omitted_values = set(omitted)
        for policy in WORKSPACE_EXPORT_REQUIRED_OMITTED_POLICIES:
            if policy not in omitted_values:
                errors.append(f"manifest omitted must include {policy!r}")

        checksums = manifest.get("checksums")
        if checksums is None:
            warnings.append("manifest checksums are missing; bundle file integrity was not verified")
        elif not isinstance(checksums, dict):
            errors.append("manifest checksums must be an object")
            checksums = {}
        for filename, checksum in (checksums.items() if isinstance(checksums, dict) else ()):
            if isinstance(filename, str) and isinstance(checksum, str) and re.fullmatch(r"[0-9a-f]{64}", checksum):
                manifest_checksums[filename] = checksum
            else:
                errors.append(f"manifest checksum must be a lowercase sha256 hex string: {filename}")

        for table in WORKSPACE_EXPORT_TABLES:
            filename = f"{table}.jsonl"
            if filename not in names:
                if table in WORKSPACE_EXPORT_OPTIONAL_TABLES:
                    if table in manifest_tables or filename in manifest_checksums:
                        errors.append(f"manifest references missing optional export table: {filename}")
                    else:
                        warnings.append(f"optional export table is missing: {filename}")
                else:
                    errors.append(f"required export table is missing: {filename}")
                continue
            expected_checksum = manifest_checksums.get(filename)
            if isinstance(checksums, dict):
                if expected_checksum is None:
                    errors.append(f"manifest is missing checksum for file: {filename}")
                else:
                    actual_checksum = _sha256_bytes(archive.read(filename))
                    if actual_checksum != expected_checksum:
                        errors.append(f"manifest checksum mismatch for {filename}: expected {expected_checksum}, found {actual_checksum}")
            rows = _read_workspace_import_jsonl(archive, filename, errors)
            table_counts[table] = len(rows)
            expected = manifest_tables.get(table)
            if expected is None:
                errors.append(f"manifest is missing row count for table: {table}")
            elif expected != len(rows):
                errors.append(f"manifest row count mismatch for {table}: expected {expected}, found {len(rows)}")

        for table in sorted(set(manifest_tables) - set(WORKSPACE_EXPORT_TABLES)):
            if table in WORKSPACE_EXPORT_OMITTED_TABLES:
                errors.append(f"omitted table must not be listed in manifest tables: {table}")
            else:
                warnings.append(f"manifest contains unknown table: {table}")
        for filename in sorted(set(manifest_checksums) - {f"{table}.jsonl" for table in WORKSPACE_EXPORT_TABLES}):
            warnings.append(f"manifest contains unknown checksum file: {filename}")

        for name in sorted(names):
            if name == "manifest.json" or name.endswith(".jsonl"):
                _scan_workspace_import_entry(archive, name, errors)
            if name.endswith(".jsonl"):
                table = name.removesuffix(".jsonl")
                if table in WORKSPACE_EXPORT_OMITTED_TABLES:
                    errors.append(f"omitted table must not be present in bundle: {name}")
                elif table not in WORKSPACE_EXPORT_TABLES:
                    warnings.append(f"bundle contains unknown JSONL file: {name}")

    return report()


def _read_workspace_import_manifest(archive: zipfile.ZipFile, errors: list[str]) -> dict[str, Any]:
    try:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    except UnicodeDecodeError:
        errors.append("manifest.json must be UTF-8")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"manifest.json is invalid JSON: line {exc.lineno} column {exc.colno}")
        return {}
    if not isinstance(manifest, dict):
        errors.append("manifest.json must contain a JSON object")
        return {}
    return manifest


def _read_workspace_import_jsonl(
    archive: zipfile.ZipFile,
    name: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    try:
        text = archive.read(name).decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{name} must be UTF-8")
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{name}:{line_number} is invalid JSON: column {exc.colno}")
            continue
        if not isinstance(row, dict):
            errors.append(f"{name}:{line_number} must contain a JSON object")
            continue
        rows.append(row)
    return rows


def _workspace_import_rows_for_insert(table: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if table == "documents":
        return [
            {
                **row,
                "source_path": row.get("source_path") or f"workspace-import://{row.get('id', 'document')}",
            }
            for row in rows
        ]
    if table == "api_token_policy":
        return [row for row in rows if row.get("updated_at")]
    if table == "query_retention_policy":
        return [row for row in rows if row.get("updated_at")]
    if table == "audit_retention_policy":
        return [row for row in rows if row.get("updated_at")]
    if table == "workspace_quota_policy":
        return [row for row in rows if row.get("updated_at") and row.get("updated_by")]
    if table == "provider_config":
        return [
            row
            for row in rows
            if row.get("configured") and row.get("base_url") and row.get("model") and row.get("updated_at") and row.get("updated_by")
        ]
    if table == "virtual_nodes":
        return [row for row in rows if row.get("axis") not in {"kind", "folder"}]
    if table == "audit_events":
        return [
            {
                **row,
                "details_json": json.dumps(row.get("details") or {}, sort_keys=True),
            }
            for row in rows
        ]
    return rows


def _scan_workspace_import_entry(archive: zipfile.ZipFile, name: str, errors: list[str]) -> None:
    try:
        text = archive.read(name).decode("utf-8")
    except UnicodeDecodeError:
        return
    forbidden_markers = (
        "pit_",
        "pis_",
        "pcs_",
        "pss_",
        "token_hash",
        "password_hash",
        "password_salt",
        "source_path",
    )
    for marker in forbidden_markers:
        if marker in text:
            errors.append(f"{name} contains forbidden export marker: {marker}")
    if _ABSOLUTE_SOURCE_PATH.search(text):
        errors.append(f"{name} appears to contain an absolute source filesystem path")


def _redact_audit_sink_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return _redact_audit_sink_mapping(value)
    if isinstance(value, list):
        return [_redact_audit_sink_value(key, item) for item in value]
    if isinstance(value, str) and _AUDIT_SINK_SECRET_VALUE.search(value):
        return "[redacted]"
    return value


def _redact_audit_sink_mapping(data: dict[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in data.items():
        if _audit_sink_secret_key(key):
            continue
        redacted[key] = _redact_audit_sink_value(key, value)
    return redacted


def _redact_public_share_text(content: Any) -> str:
    text = "" if content is None else str(content)
    text = _AUDIT_SINK_SECRET_VALUE.sub("[redacted]", text)
    text = _ABSOLUTE_SOURCE_PATH.sub(lambda match: f"{match.group(1)}[redacted-path]", text)
    text = _EMAIL_ADDRESS.sub("[redacted-email]", text)
    return text


def _redact_conversation_share_citation(citation: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(citation)
    for key in ("doc_name", "label"):
        if redacted.get(key) is not None:
            redacted[key] = _redact_public_share_text(redacted[key])
    return redacted


def _minimize_redacted_public_share_link(link: dict[str, Any], target_key: str) -> dict[str, Any]:
    public_link = dict(link)
    for key in ("id", "workspace_id", target_key, "created_by"):
        public_link.pop(key, None)
    return public_link


def _strip_public_share_link_management_fields(link: dict[str, Any]) -> dict[str, Any]:
    public_link = dict(link)
    for key in ("password_protected", "max_views", "view_count", "last_viewed_at"):
        public_link.pop(key, None)
    return public_link


def _minimize_redacted_public_entity(entity: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    public_entity = dict(entity)
    for key in keys:
        public_entity.pop(key, None)
    return public_entity


def _audit_sink_secret_key(key: str) -> bool:
    key_lower = key.casefold()
    return any(secret in key_lower for secret in ("token", "secret", "authorization", "api_key", "password"))


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _safe_storage_segment(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in ".-_" else "_" for char in value).strip(" ._")
    return safe or "workspace"


class EnterpriseStore:
    """SQLite/filesystem corpus store for the clean-room enterprise layer."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_dir = self.root / "pageindex-workspace"
        self.index_dir.mkdir(exist_ok=True)
        self.db_path = self.root / "enterprise.sqlite3"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._transaction_depth = 0
        self._pending_audit_sink_events: list[dict[str, Any]] = []
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS workspaces (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspace_members (
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'member',
              created_at TEXT NOT NULL,
              PRIMARY KEY (workspace_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS workspace_invitations (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              email TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'member',
              invited_by TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              created_at TEXT NOT NULL,
              expires_at TEXT,
              accepted_by TEXT,
              accepted_at TEXT,
              revoked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS workspace_groups (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(workspace_id, name)
            );

            CREATE TABLE IF NOT EXISTS workspace_group_members (
              group_id TEXT NOT NULL REFERENCES workspace_groups(id) ON DELETE CASCADE,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (group_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS api_tokens (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL,
              name TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL,
              expires_at TEXT,
              scopes_json TEXT,
              last_used_at TEXT
            );

            CREATE TABLE IF NOT EXISTS api_token_policies (
              workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
              default_expires_in_days INTEGER,
              rotation_due_in_days INTEGER,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspace_quota_policies (
              workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
              max_documents INTEGER,
              max_pages INTEGER,
              max_members INTEGER,
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspace_provider_configs (
              workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
              provider TEXT NOT NULL,
              base_url TEXT NOT NULL,
              model TEXT NOT NULL,
              api_key_env_var TEXT,
              timeout_seconds REAL,
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspace_audit_jsonl_sinks (
              workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
              relative_path TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_retention_policies (
              workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
              retention_days INTEGER,
              legal_hold INTEGER NOT NULL DEFAULT 0,
              legal_hold_reason TEXT,
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS query_retention_policies (
              workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
              retention_days INTEGER,
              legal_hold INTEGER NOT NULL DEFAULT 0,
              legal_hold_reason TEXT,
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
              id TEXT PRIMARY KEY,
              workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL,
              action TEXT NOT NULL,
              target_type TEXT NOT NULL,
              target_id TEXT,
              details_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              previous_integrity_hash TEXT,
              integrity_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS folders (
              id TEXT PRIMARY KEY,
              workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
              parent_id TEXT REFERENCES folders(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              path TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS folder_access_grants (
              folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'read',
              granted_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (folder_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS folder_group_access_grants (
              folder_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              group_id TEXT NOT NULL REFERENCES workspace_groups(id) ON DELETE CASCADE,
              role TEXT NOT NULL DEFAULT 'read',
              granted_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (folder_id, group_id)
            );

            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY,
              workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
              folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              source_path TEXT NOT NULL,
              kind TEXT NOT NULL,
              access_mode TEXT NOT NULL DEFAULT 'workspace',
              page_count INTEGER,
              line_count INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS document_access_grants (
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'read',
              granted_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (doc_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS document_group_access_grants (
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              group_id TEXT NOT NULL REFERENCES workspace_groups(id) ON DELETE CASCADE,
              role TEXT NOT NULL DEFAULT 'read',
              granted_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (doc_id, group_id)
            );

            CREATE TABLE IF NOT EXISTS document_share_links (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              created_by TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,
              password_salt TEXT,
              password_hash TEXT,
              redact_content INTEGER NOT NULL DEFAULT 0,
              max_views INTEGER,
              view_count INTEGER NOT NULL DEFAULT 0,
              last_viewed_at TEXT,
              created_at TEXT NOT NULL,
              expires_at TEXT,
              revoked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS query_source_sets (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              shared INTEGER NOT NULL DEFAULT 0,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(workspace_id, name)
            );

            CREATE TABLE IF NOT EXISTS query_source_set_documents (
              source_set_id TEXT NOT NULL REFERENCES query_source_sets(id) ON DELETE CASCADE,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              position INTEGER NOT NULL,
              PRIMARY KEY (source_set_id, doc_id)
            );

            CREATE TABLE IF NOT EXISTS query_source_set_share_links (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              source_set_id TEXT NOT NULL REFERENCES query_source_sets(id) ON DELETE CASCADE,
              created_by TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,
              password_salt TEXT,
              password_hash TEXT,
              redact_content INTEGER NOT NULL DEFAULT 0,
              max_views INTEGER,
              view_count INTEGER NOT NULL DEFAULT 0,
              last_viewed_at TEXT,
              created_at TEXT NOT NULL,
              expires_at TEXT,
              revoked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS document_pages (
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              page INTEGER NOT NULL,
              content TEXT NOT NULL,
              PRIMARY KEY (doc_id, page)
            );

            CREATE TABLE IF NOT EXISTS document_versions (
              id TEXT PRIMARY KEY,
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
              version INTEGER NOT NULL,
              action TEXT NOT NULL,
              actor_user_id TEXT,
              name TEXT NOT NULL,
              kind TEXT NOT NULL,
              source_name TEXT NOT NULL,
              page_count INTEGER,
              line_count INTEGER,
              created_at TEXT NOT NULL,
              UNIQUE(doc_id, version)
            );

            CREATE TABLE IF NOT EXISTS query_runs (
              id TEXT PRIMARY KEY,
              workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
              actor_user_id TEXT,
              query TEXT NOT NULL,
              scope_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS conversations (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              created_by TEXT NOT NULL,
              title TEXT NOT NULL,
              auto_title_pending INTEGER NOT NULL DEFAULT 0,
              source_set_id TEXT REFERENCES query_source_sets(id) ON DELETE SET NULL,
              folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              archived_at TEXT
            );

            CREATE TABLE IF NOT EXISTS conversation_share_links (
              id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
              created_by TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,
              password_salt TEXT,
              password_hash TEXT,
              redact_content INTEGER NOT NULL DEFAULT 0,
              max_views INTEGER,
              view_count INTEGER NOT NULL DEFAULT 0,
              last_viewed_at TEXT,
              created_at TEXT NOT NULL,
              expires_at TEXT,
              revoked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS conversation_messages (
              id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
              workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              user_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              run_id TEXT REFERENCES query_runs(id) ON DELETE SET NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL REFERENCES query_runs(id) ON DELETE CASCADE,
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              node_id TEXT,
              page_start INTEGER,
              page_end INTEGER,
              line_start INTEGER,
              line_end INTEGER,
              text TEXT NOT NULL,
              reason TEXT NOT NULL,
              score REAL NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS citations (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL REFERENCES query_runs(id) ON DELETE CASCADE,
              evidence_id TEXT NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              label TEXT NOT NULL,
              page_start INTEGER NOT NULL,
              page_end INTEGER NOT NULL,
              line_start INTEGER,
              line_end INTEGER,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS virtual_nodes (
              id TEXT PRIMARY KEY,
              parent_id TEXT REFERENCES virtual_nodes(id) ON DELETE CASCADE,
              doc_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
              axis TEXT NOT NULL,
              label TEXT NOT NULL,
              path TEXT NOT NULL UNIQUE,
              summary TEXT NOT NULL DEFAULT '',
              source_node_id TEXT,
              page_start INTEGER,
              page_end INTEGER,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS virtual_node_docs (
              virtual_node_id TEXT NOT NULL REFERENCES virtual_nodes(id) ON DELETE CASCADE,
              doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
              reason TEXT NOT NULL,
              score REAL NOT NULL DEFAULT 0,
              PRIMARY KEY (virtual_node_id, doc_id)
            );
            """
        )
        self.conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_invitations_pending_email
            ON workspace_invitations (workspace_id, email)
            WHERE status = 'pending'
            """
        )
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_query_source_set_documents_workspace
            ON query_source_set_documents (workspace_id, doc_id)
            """
        )
        self._ensure_schema_columns()
        self._commit()

    @contextmanager
    def _atomic(self):
        outer = self._transaction_depth == 0
        self._transaction_depth += 1
        try:
            yield
        except Exception:
            if outer:
                self.conn.rollback()
                self._pending_audit_sink_events.clear()
            raise
        else:
            if outer:
                self.conn.commit()
                self._flush_audit_sink_events()
        finally:
            self._transaction_depth -= 1

    def _commit(self) -> None:
        if self._transaction_depth == 0:
            self.conn.commit()
            self._flush_audit_sink_events()

    def _ensure_schema_columns(self) -> None:
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(virtual_nodes)")}
        additions = {
            "folders": {
                "workspace_id": "TEXT",
            },
            "documents": {
                "workspace_id": "TEXT",
                "access_mode": "TEXT NOT NULL DEFAULT 'workspace'",
            },
            "query_runs": {
                "workspace_id": "TEXT",
                "actor_user_id": "TEXT",
            },
            "query_source_sets": {
                "shared": "INTEGER NOT NULL DEFAULT 0",
            },
            "api_tokens": {
                "expires_at": "TEXT",
                "scopes_json": "TEXT",
                "last_used_at": "TEXT",
            },
            "audit_events": {
                "previous_integrity_hash": "TEXT",
                "integrity_hash": "TEXT",
            },
            "audit_retention_policies": {
                "legal_hold": "INTEGER NOT NULL DEFAULT 0",
                "legal_hold_reason": "TEXT",
            },
            "query_retention_policies": {
                "legal_hold": "INTEGER NOT NULL DEFAULT 0",
                "legal_hold_reason": "TEXT",
            },
            "workspace_quota_policies": {
                "max_documents": "INTEGER",
                "max_pages": "INTEGER",
                "max_members": "INTEGER",
                "updated_at": "TEXT",
                "updated_by": "TEXT",
            },
            "workspace_provider_configs": {
                "provider": "TEXT",
                "base_url": "TEXT",
                "model": "TEXT",
                "api_key_env_var": "TEXT",
                "timeout_seconds": "REAL",
                "updated_at": "TEXT",
                "updated_by": "TEXT",
            },
            "document_versions": {
                "workspace_id": "TEXT",
                "actor_user_id": "TEXT",
                "source_name": "TEXT",
                "page_count": "INTEGER",
                "line_count": "INTEGER",
            },
            "conversations": {
                "auto_title_pending": "INTEGER NOT NULL DEFAULT 0",
                "source_set_id": "TEXT REFERENCES query_source_sets(id) ON DELETE SET NULL",
                "folder_id": "TEXT REFERENCES folders(id) ON DELETE SET NULL",
                "archived_at": "TEXT",
            },
            "virtual_nodes": {
                "doc_id": "TEXT REFERENCES documents(id) ON DELETE CASCADE",
                "source_node_id": "TEXT",
                "page_start": "INTEGER",
                "page_end": "INTEGER",
            },
            "evidence": {
                "line_start": "INTEGER",
                "line_end": "INTEGER",
            },
            "citations": {
                "line_start": "INTEGER",
                "line_end": "INTEGER",
            },
            "document_share_links": {
                "revoked_at": "TEXT",
                "redact_content": "INTEGER NOT NULL DEFAULT 0",
                "max_views": "INTEGER",
                "password_salt": "TEXT",
                "password_hash": "TEXT",
                "view_count": "INTEGER NOT NULL DEFAULT 0",
                "last_viewed_at": "TEXT",
            },
            "conversation_share_links": {
                "revoked_at": "TEXT",
                "redact_content": "INTEGER NOT NULL DEFAULT 0",
                "max_views": "INTEGER",
                "password_salt": "TEXT",
                "password_hash": "TEXT",
                "view_count": "INTEGER NOT NULL DEFAULT 0",
                "last_viewed_at": "TEXT",
            },
        }
        for table, table_additions in additions.items():
            columns = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            for name, definition in table_additions.items():
                if name not in columns:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        self.conn.execute(
            "UPDATE api_tokens SET scopes_json = ? WHERE scopes_json IS NULL OR scopes_json = ''",
            (json.dumps(list(API_TOKEN_SCOPES)),),
        )
        self.conn.execute(
            "UPDATE documents SET access_mode = 'workspace' WHERE access_mode IS NULL OR access_mode = ''"
        )
        self._ensure_folder_workspace_path_index()

    def _ensure_folder_workspace_path_index(self) -> None:
        unique_indexes = []
        for index in self.conn.execute("PRAGMA index_list(folders)"):
            if index["unique"]:
                columns = [column["name"] for column in self.conn.execute(f"PRAGMA index_info({index['name']})")]
                unique_indexes.append(columns)
        if ["path"] in unique_indexes:
            self._rebuild_folders_without_global_path_unique()
            unique_indexes = []
            for index in self.conn.execute("PRAGMA index_list(folders)"):
                if index["unique"]:
                    columns = [column["name"] for column in self.conn.execute(f"PRAGMA index_info({index['name']})")]
                    unique_indexes.append(columns)
        if ["workspace_id", "path"] not in unique_indexes:
            self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_workspace_path ON folders (workspace_id, path)")

    def _rebuild_folders_without_global_path_unique(self) -> None:
        self.conn.commit()
        legacy_alter_table = self.conn.execute("PRAGMA legacy_alter_table").fetchone()[0]
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.conn.execute("PRAGMA legacy_alter_table = ON")
        try:
            self.conn.execute("ALTER TABLE folders RENAME TO folders_old")
            self.conn.execute(
                """
                CREATE TABLE folders (
                  id TEXT PRIMARY KEY,
                  workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
                  parent_id TEXT REFERENCES folders(id) ON DELETE CASCADE,
                  name TEXT NOT NULL,
                  path TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                INSERT INTO folders (id, workspace_id, parent_id, name, path, created_at)
                SELECT id, workspace_id, parent_id, name, path, created_at FROM folders_old
                """
            )
            self.conn.execute("DROP TABLE folders_old")
            self.conn.commit()
        finally:
            self.conn.execute(f"PRAGMA legacy_alter_table = {int(legacy_alter_table)}")
            self.conn.execute("PRAGMA foreign_keys = ON")

    def create_workspace(self, name: str, workspace_id: str | None = None) -> str:
        name = name.strip()
        if not name:
            raise ValueError("Workspace name is required.")
        workspace_id = workspace_id or f"ws_{uuid.uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO workspaces (id, name, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name
            """,
            (workspace_id, name, _now()),
        )
        self._commit()
        return workspace_id

    def add_workspace_member(
        self,
        workspace_id: str,
        user_id: str,
        role: str = "member",
        *,
        actor_user_id: str | None = None,
    ) -> None:
        self._require_workspace(workspace_id)
        user_id = user_id.strip()
        role = _normalize_workspace_role(role)
        if not user_id:
            raise ValueError("User id is required.")
        if actor_user_id:
            self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        previous_role = self.workspace_role(workspace_id, user_id)
        if previous_role == "owner" and role != "owner" and self._workspace_owner_count(workspace_id) <= 1:
            raise ValueError("workspace must keep at least one owner")
        if previous_role is None:
            self._enforce_workspace_quota(workspace_id, members_delta=1)
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id, user_id) DO UPDATE SET role = excluded.role
                """,
                (workspace_id, user_id, role, _now()),
            )
            if actor_user_id:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "workspace_member.upsert",
                    target_type="workspace_member",
                    target_id=user_id,
                    details={"role": role, "previous_role": previous_role},
                )

    def create_workspace_invitation(
        self,
        workspace_id: str,
        actor_user_id: str,
        email: str,
        *,
        role: str = "member",
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        email = _normalize_invitation_email(email)
        role = _normalize_workspace_role(role, invitation=True)
        expires_at = _normalize_expires_at(expires_at)
        if self._one(
            """
            SELECT id FROM workspace_invitations
            WHERE workspace_id = ? AND email = ? AND status = 'pending'
            """,
            (workspace_id, email),
        ):
            raise ValueError("pending invitation already exists")
        invitation_id = f"inv_{uuid.uuid4().hex}"
        created_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO workspace_invitations (
                    id, workspace_id, email, role, invited_by, status, created_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (invitation_id, workspace_id, email, role, actor_user_id, created_at, expires_at),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "workspace_invitation.create",
                target_type="workspace_invitation",
                target_id=invitation_id,
                details={"email": email, "role": role, "expires_at": expires_at},
            )
        return self._workspace_invitation(invitation_id)

    def list_workspace_invitations(
        self,
        workspace_id: str,
        actor_user_id: str,
        *,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        params: list[Any] = [workspace_id]
        where = "workspace_id = ?"
        if status is not None:
            status = status.strip().casefold()
            if status not in {"pending", "accepted", "revoked"}:
                raise ValueError("Unsupported invitation status")
            where += " AND status = ?"
            params.append(status)
        rows = self.conn.execute(
            f"""
            SELECT id, workspace_id, email, role, invited_by, status, created_at,
                   expires_at, accepted_by, accepted_at, revoked_at
            FROM workspace_invitations
            WHERE {where}
            ORDER BY created_at DESC, id
            """,
            params,
        )
        return [dict(row) for row in rows]

    def accept_workspace_invitation(self, invitation_id: str, user_id: str) -> dict[str, Any]:
        invitation_id = invitation_id.strip()
        if not invitation_id:
            raise ValueError("Invitation id is required.")
        user_id = _normalize_invitation_email(user_id)
        invitation = self._workspace_invitation(invitation_id)
        if invitation is None:
            raise ValueError("invitation not found")
        if invitation["status"] != "pending":
            raise ValueError("invitation is not pending")
        if _is_expired(invitation["expires_at"]):
            raise ValueError("invitation expired")
        if invitation["email"] != user_id:
            raise PermissionError("invitation does not match user")
        workspace_id = invitation["workspace_id"]
        existing_role = self.workspace_role(workspace_id, user_id)
        role = invitation["role"]
        if existing_role and WORKSPACE_ROLE_RANK[existing_role] > WORKSPACE_ROLE_RANK[role]:
            role = existing_role
        if existing_role is None:
            self._enforce_workspace_quota(workspace_id, members_delta=1)
        accepted_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO workspace_members (workspace_id, user_id, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id, user_id) DO UPDATE SET role = excluded.role
                """,
                (workspace_id, user_id, role, accepted_at),
            )
            self.conn.execute(
                """
                UPDATE workspace_invitations
                SET status = 'accepted', accepted_by = ?, accepted_at = ?
                WHERE id = ?
                """,
                (user_id, accepted_at, invitation_id),
            )
            self._insert_audit_event(
                workspace_id,
                user_id,
                "workspace_invitation.accept",
                target_type="workspace_invitation",
                target_id=invitation_id,
                details={"email": invitation["email"], "role": invitation["role"], "member_role": role},
            )
        accepted = self._workspace_invitation(invitation_id)
        assert accepted is not None
        return accepted

    def revoke_workspace_invitation(self, workspace_id: str, actor_user_id: str, invitation_id: str) -> bool:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        invitation_id = invitation_id.strip()
        if not invitation_id:
            raise ValueError("Invitation id is required.")
        invitation = self._one(
            """
            SELECT id, email, role, status FROM workspace_invitations
            WHERE workspace_id = ? AND id = ?
            """,
            (workspace_id, invitation_id),
        )
        if invitation is None or invitation["status"] != "pending":
            return False
        with self._atomic():
            self.conn.execute(
                """
                UPDATE workspace_invitations
                SET status = 'revoked', revoked_at = ?
                WHERE id = ?
                """,
                (_now(), invitation_id),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "workspace_invitation.revoke",
                target_type="workspace_invitation",
                target_id=invitation_id,
                details={"email": invitation["email"], "role": invitation["role"]},
            )
        return True

    def _workspace_invitation(self, invitation_id: str) -> dict[str, Any] | None:
        row = self._one(
            """
            SELECT id, workspace_id, email, role, invited_by, status, created_at,
                   expires_at, accepted_by, accepted_at, revoked_at
            FROM workspace_invitations
            WHERE id = ?
            """,
            (invitation_id,),
        )
        return dict(row) if row else None

    def list_workspace_members(self, workspace_id: str, actor_user_id: str) -> list[dict[str, Any]]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        rows = self.conn.execute(
            """
            SELECT workspace_id, user_id, role, created_at
            FROM workspace_members
            WHERE workspace_id = ?
            ORDER BY user_id
            """,
            (workspace_id,),
        )
        return [dict(row) for row in rows]

    def remove_workspace_member(self, workspace_id: str, user_id: str, actor_user_id: str) -> bool:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        user_id = user_id.strip()
        if not user_id:
            raise ValueError("User id is required.")
        previous_role = self.workspace_role(workspace_id, user_id)
        if not previous_role:
            return False
        if previous_role == "owner" and self._workspace_owner_count(workspace_id) <= 1:
            raise ValueError("workspace must keep at least one owner")
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id),
            )
            removed = cursor.rowcount > 0
            if removed:
                self.conn.execute(
                    "DELETE FROM workspace_group_members WHERE workspace_id = ? AND user_id = ?",
                    (workspace_id, user_id),
                )
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "workspace_member.remove",
                    target_type="workspace_member",
                    target_id=user_id,
                    details={"previous_role": previous_role},
                )
        return removed

    def create_workspace_group(
        self,
        workspace_id: str,
        actor_user_id: str,
        name: str,
        *,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        name = name.strip()
        if not name:
            raise ValueError("Group name is required.")
        group_id = group_id or f"grp_{uuid.uuid4().hex}"
        if "/" in group_id or "%" in group_id:
            raise ValueError("group_id must be URL-safe")
        created_at = _now()
        try:
            with self._atomic():
                self.conn.execute(
                    """
                    INSERT INTO workspace_groups (id, workspace_id, name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (group_id, workspace_id, name, created_at),
                )
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "workspace_group.create",
                    target_type="workspace_group",
                    target_id=group_id,
                    details={"name": name},
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Group name already exists in this workspace.") from exc
        group = self._workspace_group(workspace_id, group_id)
        assert group is not None
        return group

    def list_workspace_groups(self, workspace_id: str, actor_user_id: str) -> list[dict[str, Any]]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        rows = self.conn.execute(
            """
            SELECT g.id, g.workspace_id, g.name, g.created_at,
                   COUNT(gm.user_id) AS member_count
            FROM workspace_groups g
            LEFT JOIN workspace_group_members gm ON gm.group_id = g.id
            WHERE g.workspace_id = ?
            GROUP BY g.id
            ORDER BY g.name, g.id
            """,
            (workspace_id,),
        )
        return [dict(row) for row in rows]

    def get_workspace_usage_summary(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)

        def count(sql: str, args: tuple[Any, ...] = (workspace_id,)) -> int:
            row = self.conn.execute(sql, args).fetchone()
            return int(row["count"]) if row else 0

        def grouped(sql: str, args: tuple[Any, ...] = (workspace_id,)) -> dict[str, int]:
            return {str(row["name"]): int(row["count"]) for row in self.conn.execute(sql, args)}

        latest_audit = self.conn.execute(
            "SELECT MAX(created_at) AS created_at FROM audit_events WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        share_now = _now()
        virtual_nodes = self.conn.execute(
            """
            SELECT COUNT(DISTINCT n.id) AS count
            FROM virtual_nodes n
            LEFT JOIN virtual_node_docs vnd ON vnd.virtual_node_id = n.id
            LEFT JOIN documents vd ON vd.id = vnd.doc_id
            LEFT JOIN documents nd ON nd.id = n.doc_id
            WHERE vd.workspace_id = ? OR nd.workspace_id = ?
            """,
            (workspace_id, workspace_id),
        ).fetchone()
        return {
            "workspace_id": workspace_id,
            "documents": {
                "count": count("SELECT COUNT(*) AS count FROM documents WHERE workspace_id = ?"),
                "pages": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM document_pages p
                    JOIN documents d ON d.id = p.doc_id
                    WHERE d.workspace_id = ?
                    """
                ),
                "versions": count("SELECT COUNT(*) AS count FROM document_versions WHERE workspace_id = ?"),
                "restricted": count(
                    "SELECT COUNT(*) AS count FROM documents WHERE workspace_id = ? AND access_mode = 'restricted'"
                ),
                "by_kind": grouped(
                    """
                    SELECT kind AS name, COUNT(*) AS count
                    FROM documents
                    WHERE workspace_id = ?
                    GROUP BY kind
                    ORDER BY kind
                    """
                ),
            },
            "share_links": {
                "active": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM document_share_links
                    WHERE workspace_id = ?
                      AND revoked_at IS NULL
                      AND (expires_at IS NULL OR expires_at > ?)
                      AND (max_views IS NULL OR view_count < max_views)
                    """,
                    (workspace_id, share_now),
                ),
                "revoked": count(
                    "SELECT COUNT(*) AS count FROM document_share_links WHERE workspace_id = ? AND revoked_at IS NOT NULL"
                ),
                "expired": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM document_share_links
                    WHERE workspace_id = ?
                      AND revoked_at IS NULL
                      AND expires_at IS NOT NULL
                      AND expires_at <= ?
                    """,
                    (workspace_id, share_now),
                ),
            },
            "team": {
                "members": count("SELECT COUNT(*) AS count FROM workspace_members WHERE workspace_id = ?"),
                "members_by_role": grouped(
                    """
                    SELECT role AS name, COUNT(*) AS count
                    FROM workspace_members
                    WHERE workspace_id = ?
                    GROUP BY role
                    ORDER BY role
                    """
                ),
                "groups": count("SELECT COUNT(*) AS count FROM workspace_groups WHERE workspace_id = ?"),
                "group_members": count("SELECT COUNT(*) AS count FROM workspace_group_members WHERE workspace_id = ?"),
                "invitations_by_status": grouped(
                    """
                    SELECT status AS name, COUNT(*) AS count
                    FROM workspace_invitations
                    WHERE workspace_id = ?
                    GROUP BY status
                    ORDER BY status
                    """
                ),
            },
            "api_tokens": {
                "active": count("SELECT COUNT(*) AS count FROM api_tokens WHERE workspace_id = ?"),
                "with_expiration": count(
                    "SELECT COUNT(*) AS count FROM api_tokens WHERE workspace_id = ? AND expires_at IS NOT NULL"
                ),
            },
            "conversations": {
                "count": count("SELECT COUNT(*) AS count FROM conversations WHERE workspace_id = ?"),
                "messages": count("SELECT COUNT(*) AS count FROM conversation_messages WHERE workspace_id = ?"),
                "share_links_active": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM conversation_share_links
                    WHERE workspace_id = ?
                      AND revoked_at IS NULL
                      AND (expires_at IS NULL OR expires_at > ?)
                      AND (max_views IS NULL OR view_count < max_views)
                    """,
                    (workspace_id, share_now),
                ),
                "share_links_revoked": count(
                    "SELECT COUNT(*) AS count FROM conversation_share_links WHERE workspace_id = ? AND revoked_at IS NOT NULL"
                ),
            },
            "source_sets": {
                "count": count("SELECT COUNT(*) AS count FROM query_source_sets WHERE workspace_id = ?"),
                "shared": count("SELECT COUNT(*) AS count FROM query_source_sets WHERE workspace_id = ? AND shared = 1"),
                "documents": count(
                    "SELECT COUNT(*) AS count FROM query_source_set_documents WHERE workspace_id = ?"
                ),
                "share_links_active": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM query_source_set_share_links
                    WHERE workspace_id = ?
                      AND revoked_at IS NULL
                      AND (expires_at IS NULL OR expires_at > ?)
                      AND (max_views IS NULL OR view_count < max_views)
                    """,
                    (workspace_id, share_now),
                ),
                "share_links_revoked": count(
                    "SELECT COUNT(*) AS count FROM query_source_set_share_links WHERE workspace_id = ? AND revoked_at IS NOT NULL"
                ),
                "share_links_expired": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM query_source_set_share_links
                    WHERE workspace_id = ?
                      AND revoked_at IS NULL
                      AND expires_at IS NOT NULL
                      AND expires_at <= ?
                    """,
                    (workspace_id, share_now),
                ),
                "share_links_exhausted": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM query_source_set_share_links
                    WHERE workspace_id = ?
                      AND revoked_at IS NULL
                      AND (expires_at IS NULL OR expires_at > ?)
                      AND max_views IS NOT NULL
                      AND view_count >= max_views
                    """,
                    (workspace_id, share_now),
                ),
            },
            "retrieval": {
                "query_runs": count("SELECT COUNT(*) AS count FROM query_runs WHERE workspace_id = ?"),
                "evidence": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM evidence e
                    JOIN query_runs q ON q.id = e.run_id
                    WHERE q.workspace_id = ?
                    """
                ),
                "citations": count(
                    """
                    SELECT COUNT(*) AS count
                    FROM citations c
                    JOIN query_runs q ON q.id = c.run_id
                    WHERE q.workspace_id = ?
                    """
                ),
                "virtual_nodes": int(virtual_nodes["count"]) if virtual_nodes else 0,
            },
            "audit": {
                "events": count("SELECT COUNT(*) AS count FROM audit_events WHERE workspace_id = ?"),
                "latest_event_at": latest_audit["created_at"] if latest_audit else None,
            },
        }

    def _workspace_quota_usage(self, workspace_id: str) -> dict[str, int]:
        documents = int(
            self.conn.execute(
                "SELECT COUNT(*) AS count FROM documents WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()["count"]
        )
        pages = int(
            self.conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM document_pages p
                JOIN documents d ON d.id = p.doc_id
                WHERE d.workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()["count"]
        )
        members = int(
            self.conn.execute(
                "SELECT COUNT(*) AS count FROM workspace_members WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()["count"]
        )
        return {"documents": documents, "pages": pages, "members": members}

    def _workspace_quota_policy(self, workspace_id: str) -> dict[str, Any]:
        self._require_workspace(workspace_id)
        row = self._one(
            """
            SELECT workspace_id, max_documents, max_pages, max_members, updated_at, updated_by
            FROM workspace_quota_policies
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )
        if row:
            return dict(row)
        return {
            "workspace_id": workspace_id,
            "max_documents": None,
            "max_pages": None,
            "max_members": None,
            "updated_at": None,
            "updated_by": None,
        }

    def _quota_violations(self, policy: dict[str, Any], usage: dict[str, int]) -> list[str]:
        violations = []
        limits = {
            "documents": policy.get("max_documents"),
            "pages": policy.get("max_pages"),
            "members": policy.get("max_members"),
        }
        for name, limit in limits.items():
            if limit is not None and usage[name] > int(limit):
                violations.append(name)
        return violations

    def get_workspace_quota_policy(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        policy = self._workspace_quota_policy(workspace_id)
        usage = self._workspace_quota_usage(workspace_id)
        violations = self._quota_violations(policy, usage)
        return {
            **policy,
            "usage": usage,
            "violations": violations,
            "within_quota": not violations,
        }

    def set_workspace_quota_policy(
        self,
        workspace_id: str,
        actor_user_id: str,
        *,
        max_documents: int | None | object = _UNSET,
        max_pages: int | None | object = _UNSET,
        max_members: int | None | object = _UNSET,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        if max_documents is _UNSET and max_pages is _UNSET and max_members is _UNSET:
            raise ValueError("workspace quota policy update is required")
        current = self._workspace_quota_policy(workspace_id)
        next_limits = {
            "max_documents": current["max_documents"]
            if max_documents is _UNSET
            else _normalize_quota_limit(max_documents, "max_documents"),
            "max_pages": current["max_pages"]
            if max_pages is _UNSET
            else _normalize_quota_limit(max_pages, "max_pages"),
            "max_members": current["max_members"]
            if max_members is _UNSET
            else _normalize_quota_limit(max_members, "max_members"),
        }
        usage = self._workspace_quota_usage(workspace_id)
        for limit_name, usage_name in (
            ("max_documents", "documents"),
            ("max_pages", "pages"),
            ("max_members", "members"),
        ):
            limit = next_limits[limit_name]
            if limit is not None and usage[usage_name] > limit:
                raise ValueError(f"{limit_name} is below current usage")
        updated_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO workspace_quota_policies (
                  workspace_id, max_documents, max_pages, max_members, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                  max_documents = excluded.max_documents,
                  max_pages = excluded.max_pages,
                  max_members = excluded.max_members,
                  updated_at = excluded.updated_at,
                  updated_by = excluded.updated_by
                """,
                (
                    workspace_id,
                    next_limits["max_documents"],
                    next_limits["max_pages"],
                    next_limits["max_members"],
                    updated_at,
                    actor_user_id.strip(),
                ),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id.strip(),
                "workspace.quota_policy_update",
                target_type="workspace_quota_policy",
                target_id=workspace_id,
                details=next_limits,
            )
        return self.get_workspace_quota_policy(workspace_id, actor_user_id)

    def _enforce_workspace_quota(
        self,
        workspace_id: str | None,
        *,
        documents_delta: int = 0,
        pages_delta: int = 0,
        members_delta: int = 0,
    ) -> None:
        if not workspace_id:
            return
        deltas = {
            "documents": max(0, documents_delta),
            "pages": max(0, pages_delta),
            "members": max(0, members_delta),
        }
        if not any(deltas.values()):
            return
        policy = self._workspace_quota_policy(workspace_id)
        usage = self._workspace_quota_usage(workspace_id)
        projected = {name: usage[name] + delta for name, delta in deltas.items()}
        violations = self._quota_violations(policy, projected)
        if violations:
            raise ValueError(f"workspace quota exceeded: {', '.join(violations)}")

    def rename_workspace_group(
        self,
        workspace_id: str,
        actor_user_id: str,
        group_id: str,
        name: str,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._require_workspace_group(workspace_id, group_id)
        name = name.strip()
        if not name:
            raise ValueError("Group name is required.")
        if name == group["name"]:
            return group
        try:
            with self._atomic():
                self.conn.execute(
                    "UPDATE workspace_groups SET name = ? WHERE workspace_id = ? AND id = ?",
                    (name, workspace_id, group["id"]),
                )
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "workspace_group.rename",
                    target_type="workspace_group",
                    target_id=group["id"],
                    details={"previous_name": group["name"], "name": name},
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Group name already exists in this workspace.") from exc
        updated = self._workspace_group(workspace_id, group["id"])
        assert updated is not None
        return updated

    def delete_workspace_group(self, workspace_id: str, actor_user_id: str, group_id: str) -> bool:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._workspace_group(workspace_id, group_id)
        if group is None:
            return False
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM workspace_groups WHERE workspace_id = ? AND id = ?",
                (workspace_id, group["id"]),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "workspace_group.delete",
                    target_type="workspace_group",
                    target_id=group["id"],
                    details={"name": group["name"]},
                )
        return deleted

    def list_workspace_group_members(
        self,
        workspace_id: str,
        actor_user_id: str,
        group_id: str,
    ) -> list[dict[str, Any]]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._require_workspace_group(workspace_id, group_id)
        rows = self.conn.execute(
            """
            SELECT group_id, workspace_id, user_id, created_at
            FROM workspace_group_members
            WHERE workspace_id = ? AND group_id = ?
            ORDER BY user_id
            """,
            (workspace_id, group["id"]),
        )
        return [dict(row) for row in rows]

    def add_workspace_group_member(
        self,
        workspace_id: str,
        actor_user_id: str,
        group_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._require_workspace_group(workspace_id, group_id)
        user_id = user_id.strip()
        if not user_id:
            raise ValueError("User id is required.")
        self.require_workspace_access(workspace_id, user_id)
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO workspace_group_members (group_id, workspace_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(group_id, user_id) DO UPDATE SET created_at = excluded.created_at
                """,
                (group["id"], workspace_id, user_id, _now()),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "workspace_group_member.add",
                target_type="workspace_group",
                target_id=group["id"],
                details={"user_id": user_id, "group_name": group["name"]},
            )
        updated = self._workspace_group(workspace_id, group["id"])
        assert updated is not None
        return updated

    def remove_workspace_group_member(
        self,
        workspace_id: str,
        actor_user_id: str,
        group_id: str,
        user_id: str,
    ) -> bool:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._require_workspace_group(workspace_id, group_id)
        user_id = user_id.strip()
        if not user_id:
            raise ValueError("User id is required.")
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM workspace_group_members WHERE workspace_id = ? AND group_id = ? AND user_id = ?",
                (workspace_id, group["id"], user_id),
            )
            removed = cursor.rowcount > 0
            if removed:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "workspace_group_member.remove",
                    target_type="workspace_group",
                    target_id=group["id"],
                    details={"user_id": user_id, "group_name": group["name"]},
                )
        return removed

    def _workspace_group(self, workspace_id: str, group_id: str) -> dict[str, Any] | None:
        row = self._one(
            """
            SELECT g.id, g.workspace_id, g.name, g.created_at,
                   COUNT(gm.user_id) AS member_count
            FROM workspace_groups g
            LEFT JOIN workspace_group_members gm ON gm.group_id = g.id
            WHERE g.workspace_id = ? AND g.id = ?
            GROUP BY g.id
            """,
            (workspace_id, group_id.strip()),
        )
        return dict(row) if row else None

    def _require_workspace_group(self, workspace_id: str, group_id: str) -> dict[str, Any]:
        group = self._workspace_group(workspace_id, group_id)
        if not group:
            raise ValueError(f"Group not found: {group_id}")
        return group

    def _workspace_owner_count(self, workspace_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS count FROM workspace_members WHERE workspace_id = ? AND role = 'owner'",
            (workspace_id,),
        ).fetchone()
        return int(row["count"])

    def user_can_access_workspace(self, workspace_id: str, user_id: str) -> bool:
        return bool(
            self._one(
                "SELECT 1 FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                (workspace_id, user_id),
            )
        )

    def workspace_role(self, workspace_id: str, user_id: str) -> str | None:
        row = self._one(
            "SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
            (workspace_id, user_id.strip()),
        )
        return row["role"] if row else None

    def require_workspace_access(self, workspace_id: str, user_id: str) -> None:
        self._require_workspace(workspace_id)
        if not user_id.strip() or not self.user_can_access_workspace(workspace_id, user_id):
            raise PermissionError("workspace access denied")

    def require_workspace_role(self, workspace_id: str, user_id: str, allowed_roles: set[str]) -> None:
        self.require_workspace_access(workspace_id, user_id)
        if self.workspace_role(workspace_id, user_id) not in allowed_roles:
            raise PermissionError("workspace role denied")

    def require_workspace_write(self, workspace_id: str | None, actor_user_id: str | None) -> None:
        if not workspace_id:
            return
        if not actor_user_id:
            raise PermissionError("actor_user_id is required for workspace writes")
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_WRITE_ROLES)

    def _document_read_condition(self, alias: str, actor_user_id: str | None) -> tuple[str, list[Any]]:
        if not actor_user_id:
            return "1 = 1", []
        actor_user_id = actor_user_id.strip()
        return (
            f"""
            (
              {alias}.access_mode = 'workspace'
              OR EXISTS (
                SELECT 1 FROM workspace_members wm
                WHERE wm.workspace_id = {alias}.workspace_id
                  AND wm.user_id = ?
                  AND wm.role IN ('owner', 'admin')
              )
              OR EXISTS (
                SELECT 1 FROM document_access_grants dag
                WHERE dag.doc_id = {alias}.id
                  AND dag.user_id = ?
              )
              OR EXISTS (
                SELECT 1
                FROM document_group_access_grants dgag
                JOIN workspace_group_members wgm ON wgm.group_id = dgag.group_id
                WHERE dgag.doc_id = {alias}.id
                  AND wgm.workspace_id = {alias}.workspace_id
                  AND wgm.user_id = ?
              )
              OR EXISTS (
                SELECT 1
                FROM folder_access_grants fag
                JOIN folders granted_folder ON granted_folder.id = fag.folder_id
                JOIN folders document_folder ON document_folder.id = {alias}.folder_id
                WHERE fag.workspace_id = {alias}.workspace_id
                  AND fag.user_id = ?
                  AND (
                    document_folder.path = granted_folder.path
                    OR substr(document_folder.path, 1, length(granted_folder.path) + 1) = granted_folder.path || '/'
                  )
              )
              OR EXISTS (
                SELECT 1
                FROM folder_group_access_grants fgag
                JOIN folders granted_folder ON granted_folder.id = fgag.folder_id
                JOIN folders document_folder ON document_folder.id = {alias}.folder_id
                JOIN workspace_group_members wgm ON wgm.group_id = fgag.group_id
                WHERE fgag.workspace_id = {alias}.workspace_id
                  AND wgm.workspace_id = {alias}.workspace_id
                  AND wgm.user_id = ?
                  AND (
                    document_folder.path = granted_folder.path
                    OR substr(document_folder.path, 1, length(granted_folder.path) + 1) = granted_folder.path || '/'
                  )
              )
            )
            """,
            [actor_user_id, actor_user_id, actor_user_id, actor_user_id, actor_user_id],
        )

    def _can_read_document(self, document: dict[str, Any], actor_user_id: str | None) -> bool:
        if not document.get("workspace_id") or document.get("access_mode", "workspace") == "workspace":
            return True
        if not actor_user_id:
            return False
        actor_user_id = actor_user_id.strip()
        if self.workspace_role(document["workspace_id"], actor_user_id) in WORKSPACE_ADMIN_ROLES:
            return True
        return bool(
            self._one(
                "SELECT 1 FROM document_access_grants WHERE doc_id = ? AND user_id = ?",
                (document["id"], actor_user_id),
            )
            or self._one(
                """
                SELECT 1
                FROM document_group_access_grants dgag
                JOIN workspace_group_members wgm ON wgm.group_id = dgag.group_id
                WHERE dgag.doc_id = ?
                  AND wgm.workspace_id = ?
                  AND wgm.user_id = ?
                """,
                (document["id"], document["workspace_id"], actor_user_id),
            )
            or self._one(
                """
                SELECT 1
                FROM folder_access_grants fag
                JOIN folders granted_folder ON granted_folder.id = fag.folder_id
                JOIN folders document_folder ON document_folder.id = ?
                WHERE fag.workspace_id = ?
                  AND fag.user_id = ?
                  AND (
                    document_folder.path = granted_folder.path
                    OR substr(document_folder.path, 1, length(granted_folder.path) + 1) = granted_folder.path || '/'
                  )
                """,
                (document["folder_id"], document["workspace_id"], actor_user_id),
            )
            or self._one(
                """
                SELECT 1
                FROM folder_group_access_grants fgag
                JOIN folders granted_folder ON granted_folder.id = fgag.folder_id
                JOIN folders document_folder ON document_folder.id = ?
                JOIN workspace_group_members wgm ON wgm.group_id = fgag.group_id
                WHERE fgag.workspace_id = ?
                  AND wgm.workspace_id = ?
                  AND wgm.user_id = ?
                  AND (
                    document_folder.path = granted_folder.path
                    OR substr(document_folder.path, 1, length(granted_folder.path) + 1) = granted_folder.path || '/'
                  )
                """,
                (document["folder_id"], document["workspace_id"], document["workspace_id"], actor_user_id),
            )
        )

    def _can_write_document(self, document: dict[str, Any], actor_user_id: str | None) -> bool:
        if not document.get("workspace_id") or document.get("access_mode", "workspace") == "workspace":
            return True
        if not actor_user_id:
            return False
        actor_user_id = actor_user_id.strip()
        role = self.workspace_role(document["workspace_id"], actor_user_id)
        if role in WORKSPACE_ADMIN_ROLES:
            return True
        if role not in WORKSPACE_WRITE_ROLES:
            return False
        return bool(
            self._one(
                "SELECT 1 FROM document_access_grants WHERE doc_id = ? AND user_id = ? AND role = 'write'",
                (document["id"], actor_user_id),
            )
            or self._one(
                """
                SELECT 1
                FROM document_group_access_grants dgag
                JOIN workspace_group_members wgm ON wgm.group_id = dgag.group_id
                WHERE dgag.doc_id = ?
                  AND dgag.role = 'write'
                  AND wgm.workspace_id = ?
                  AND wgm.user_id = ?
                """,
                (document["id"], document["workspace_id"], actor_user_id),
            )
        )

    def _require_document_write(self, document: dict[str, Any], actor_user_id: str | None) -> None:
        self.require_workspace_write(document.get("workspace_id"), actor_user_id)
        if document.get("workspace_id") and not self._can_write_document(document, actor_user_id):
            raise PermissionError("document write access denied")

    def create_api_token(
        self,
        workspace_id: str,
        user_id: str,
        name: str = "default",
        *,
        expires_at: str | None = None,
        scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        self.require_workspace_access(workspace_id, user_id)
        user_id = user_id.strip()
        name = name.strip() or "default"
        expires_at = _normalize_expires_at(expires_at)
        policy = self._api_token_policy(workspace_id)
        policy_default_applied = expires_at is None and policy["default_expires_in_days"] is not None
        if policy_default_applied:
            expires_at = expires_at_from_days(policy["default_expires_in_days"])
        role = self.workspace_role(workspace_id, user_id)
        allowed_scopes = _api_token_scopes_for_role(role)
        requested_scopes = _normalize_api_token_scopes(scopes) if scopes is not None else allowed_scopes
        unsupported_for_role = [scope for scope in requested_scopes if scope not in allowed_scopes]
        if unsupported_for_role:
            raise PermissionError(f"api token scope not allowed for workspace role: {unsupported_for_role[0]}")
        scopes = requested_scopes
        scopes_json = json.dumps(scopes)
        token = f"pit_{secrets.token_urlsafe(32)}"
        token_id = f"tok_{uuid.uuid4().hex}"
        created_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO api_tokens (id, workspace_id, user_id, name, token_hash, created_at, expires_at, scopes_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (token_id, workspace_id, user_id, name, _hash_token(token), created_at, expires_at, scopes_json),
            )
            self._insert_audit_event(
                workspace_id,
                user_id,
                "api_token.create",
                target_type="api_token",
                target_id=token_id,
                details={
                    "name": name,
                    "expires_at": expires_at,
                    "scopes": scopes,
                    "policy_default_applied": policy_default_applied,
                },
            )
        return {
            "id": token_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "name": name,
            "expires_at": expires_at,
            "scopes": scopes,
            **_rotation_metadata(created_at, policy["rotation_due_in_days"]),
            "token": token,
        }

    def _api_token_policy(self, workspace_id: str) -> dict[str, Any]:
        self._require_workspace(workspace_id)
        row = self._one(
            """
            SELECT workspace_id, default_expires_in_days, rotation_due_in_days, updated_at
            FROM api_token_policies
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )
        if row:
            return dict(row)
        return {
            "workspace_id": workspace_id,
            "default_expires_in_days": None,
            "rotation_due_in_days": None,
            "updated_at": None,
        }

    def get_api_token_policy(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        return self._api_token_policy(workspace_id)

    def set_api_token_policy(
        self,
        workspace_id: str,
        actor_user_id: str,
        *,
        default_expires_in_days: int | None | object = _UNSET,
        rotation_due_in_days: int | None | object = _UNSET,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        current = self._api_token_policy(workspace_id)
        default_days = current["default_expires_in_days"]
        rotation_days = current["rotation_due_in_days"]
        if default_expires_in_days is not _UNSET:
            default_days = _normalize_policy_days(default_expires_in_days, "default_expires_in_days")
        if rotation_due_in_days is not _UNSET:
            rotation_days = _normalize_policy_days(rotation_due_in_days, "rotation_due_in_days")
        updated_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO api_token_policies (workspace_id, default_expires_in_days, rotation_due_in_days, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                  default_expires_in_days = excluded.default_expires_in_days,
                  rotation_due_in_days = excluded.rotation_due_in_days,
                  updated_at = excluded.updated_at
                """,
                (workspace_id, default_days, rotation_days, updated_at),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id.strip(),
                "api_token.policy_update",
                target_type="api_token_policy",
                target_id=workspace_id,
                details={
                    "default_expires_in_days": default_days,
                    "rotation_due_in_days": rotation_days,
                },
            )
        return self._api_token_policy(workspace_id)

    def get_workspace_provider_config(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        return self._workspace_provider_config_metadata(workspace_id)

    def set_workspace_provider_config(
        self,
        workspace_id: str,
        actor_user_id: str,
        *,
        base_url: str,
        model: str,
        api_key_env_var: str | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        base_url = base_url.strip()
        model = model.strip()
        api_key_env_var = _normalize_provider_env_var(api_key_env_var)
        timeout_seconds = _normalize_provider_timeout(timeout_seconds)
        if not model:
            raise ValueError("model is required")
        validate_openai_compatible_config(
            base_url=base_url,
            api_key=os.environ.get(api_key_env_var) if api_key_env_var else None,
            model=model,
            timeout=timeout_seconds,
        )
        updated_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO workspace_provider_configs (
                  workspace_id, provider, base_url, model, api_key_env_var,
                  timeout_seconds, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                  provider = excluded.provider,
                  base_url = excluded.base_url,
                  model = excluded.model,
                  api_key_env_var = excluded.api_key_env_var,
                  timeout_seconds = excluded.timeout_seconds,
                  updated_at = excluded.updated_at,
                  updated_by = excluded.updated_by
                """,
                (
                    workspace_id,
                    "openai-compatible",
                    base_url,
                    model,
                    api_key_env_var,
                    timeout_seconds,
                    updated_at,
                    actor_user_id.strip(),
                ),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id.strip(),
                "provider_config.set",
                target_type="provider_config",
                target_id=workspace_id,
                details={
                    "provider": "openai-compatible",
                    "model": model,
                    "credential_configured": bool(api_key_env_var and os.environ.get(api_key_env_var)),
                    "timeout_seconds": timeout_seconds,
                },
            )
        return self._workspace_provider_config_metadata(workspace_id)

    def clear_workspace_provider_config(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        with self._atomic():
            self.conn.execute("DELETE FROM workspace_provider_configs WHERE workspace_id = ?", (workspace_id,))
            self._insert_audit_event(
                workspace_id,
                actor_user_id.strip(),
                "provider_config.clear",
                target_type="provider_config",
                target_id=workspace_id,
                details={},
            )
        return self._workspace_provider_config_metadata(workspace_id)

    def workspace_provider_request_options(self, workspace_id: str, fallback_model: str) -> dict[str, Any]:
        row = self._one(
            """
            SELECT provider, base_url, model, api_key_env_var, timeout_seconds
            FROM workspace_provider_configs
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )
        if not row:
            return {"model": fallback_model}
        api_key_env_var = row["api_key_env_var"]
        return {
            "model": row["model"],
            "base_url": row["base_url"],
            "api_key": os.environ.get(api_key_env_var) if api_key_env_var else None,
            "timeout": row["timeout_seconds"],
            "prefer_env_model": False,
            "prefer_env_api_key": False,
        }

    def get_workspace_audit_jsonl_sink_config(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        return self._workspace_audit_jsonl_sink_config(workspace_id)

    def set_workspace_audit_jsonl_sink_config(
        self,
        workspace_id: str,
        actor_user_id: str,
        *,
        relative_path: str,
        enabled: bool = True,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")
        normalized_path = _normalize_audit_sink_relative_path(relative_path)
        updated_at = _now()
        actor_user_id = actor_user_id.strip()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO workspace_audit_jsonl_sinks (
                  workspace_id, relative_path, enabled, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                  relative_path = excluded.relative_path,
                  enabled = excluded.enabled,
                  updated_at = excluded.updated_at,
                  updated_by = excluded.updated_by
                """,
                (workspace_id, normalized_path, int(enabled), updated_at, actor_user_id),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "audit_sink.config_update",
                target_type="audit_sink",
                target_id=workspace_id,
                details={"relative_path": normalized_path, "enabled": enabled},
            )
        return self._workspace_audit_jsonl_sink_config(workspace_id)

    def clear_workspace_audit_jsonl_sink_config(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        actor_user_id = actor_user_id.strip()
        with self._atomic():
            self.conn.execute("DELETE FROM workspace_audit_jsonl_sinks WHERE workspace_id = ?", (workspace_id,))
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "audit_sink.config_clear",
                target_type="audit_sink",
                target_id=workspace_id,
                details={},
            )
        return self._workspace_audit_jsonl_sink_config(workspace_id)

    def _workspace_audit_jsonl_sink_config(self, workspace_id: str) -> dict[str, Any]:
        self._require_workspace(workspace_id)
        row = self._one(
            """
            SELECT workspace_id, relative_path, enabled, updated_at, updated_by
            FROM workspace_audit_jsonl_sinks
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )
        if not row:
            return {
                "workspace_id": workspace_id,
                "configured": False,
                "relative_path": None,
                "enabled": False,
                "updated_at": None,
                "updated_by": None,
            }
        config = dict(row)
        config["configured"] = True
        config["enabled"] = bool(config["enabled"])
        return config

    def _workspace_provider_config_metadata(self, workspace_id: str) -> dict[str, Any]:
        self._require_workspace(workspace_id)
        row = self._one(
            """
            SELECT workspace_id, provider, base_url, model, api_key_env_var,
                   timeout_seconds, updated_at, updated_by
            FROM workspace_provider_configs
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )
        if not row:
            return {
                "workspace_id": workspace_id,
                "configured": False,
                "provider": "openai-compatible",
                "base_url": None,
                "model": None,
                "api_key_env_var": None,
                "api_key_configured": False,
                "timeout_seconds": None,
                "updated_at": None,
                "updated_by": None,
            }
        config = dict(row)
        config["configured"] = True
        config["api_key_configured"] = bool(config["api_key_env_var"] and os.environ.get(config["api_key_env_var"]))
        return config

    def verify_api_token(self, token: str) -> dict[str, Any] | None:
        token = token.strip()
        if not token:
            return None
        token_hash = _hash_token(token)
        row = self._one("SELECT * FROM api_tokens WHERE token_hash = ?", (token_hash,))
        if not row or not hmac.compare_digest(row["token_hash"], token_hash):
            return None
        if not self.user_can_access_workspace(row["workspace_id"], row["user_id"]):
            return None
        if _is_expired(row["expires_at"]):
            return None
        scopes = _decode_api_token_scopes(row["scopes_json"])
        if scopes is None:
            return None
        self.conn.execute("UPDATE api_tokens SET last_used_at = ? WHERE id = ?", (_now(), row["id"]))
        self._commit()
        return {
            "id": row["id"],
            "workspace_id": row["workspace_id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "expires_at": row["expires_at"],
            "scopes": scopes,
        }

    def list_api_tokens(
        self,
        workspace_id: str,
        actor_user_id: str,
        token_owner_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        actor_user_id = actor_user_id.strip()
        token_owner_user_id = _token_owner_user_id(actor_user_id, token_owner_user_id)
        self.require_workspace_access(workspace_id, actor_user_id)
        rows = self.conn.execute(
            """
            SELECT id, workspace_id, user_id, name, created_at, expires_at, scopes_json, last_used_at
            FROM api_tokens
            WHERE workspace_id = ? AND user_id = ?
            ORDER BY created_at DESC, name
            """,
            (workspace_id, token_owner_user_id),
        )
        tokens = []
        policy = self._api_token_policy(workspace_id)
        for row in rows:
            token = dict(row)
            token["scopes"] = _decode_api_token_scopes(token.pop("scopes_json")) or []
            token.update(_rotation_metadata(token["created_at"], policy["rotation_due_in_days"]))
            tokens.append(token)
        return tokens

    def revoke_api_token(
        self,
        workspace_id: str,
        actor_user_id: str,
        token_id: str,
        token_owner_user_id: str | None = None,
    ) -> bool:
        actor_user_id = actor_user_id.strip()
        token_owner_user_id = _token_owner_user_id(actor_user_id, token_owner_user_id)
        self.require_workspace_access(workspace_id, actor_user_id)
        token_id = token_id.strip()
        if not token_id:
            raise ValueError("Token id is required.")
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM api_tokens WHERE id = ? AND workspace_id = ? AND user_id = ?",
                (token_id, workspace_id, token_owner_user_id),
            )
            revoked = cursor.rowcount > 0
            if revoked:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "api_token.revoke",
                    target_type="api_token",
                    target_id=token_id,
                    details={"token_owner_user_id": token_owner_user_id},
                )
        return revoked

    def rotate_api_token(
        self,
        workspace_id: str,
        actor_user_id: str,
        token_id: str,
        token_owner_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        actor_user_id = actor_user_id.strip()
        token_owner_user_id = _token_owner_user_id(actor_user_id, token_owner_user_id)
        self.require_workspace_access(workspace_id, actor_user_id)
        token_id = token_id.strip()
        if not token_id:
            raise ValueError("Token id is required.")
        token = f"pit_{secrets.token_urlsafe(32)}"
        replacement_id = f"tok_{uuid.uuid4().hex}"
        created_at = _now()
        policy = self._api_token_policy(workspace_id)
        with self._atomic():
            current = self._one(
                """
                SELECT id, workspace_id, user_id, name, expires_at, scopes_json
                FROM api_tokens
                WHERE id = ? AND workspace_id = ? AND user_id = ?
                """,
                (token_id, workspace_id, token_owner_user_id),
            )
            if not current:
                return None
            scopes = _decode_api_token_scopes(current["scopes_json"])
            if scopes is None:
                raise ValueError("Stored api token scopes are invalid.")
            scopes = _cap_api_token_scopes_to_role(scopes, self.workspace_role(workspace_id, token_owner_user_id))
            if not scopes:
                raise PermissionError("api token scope not allowed for workspace role")
            self.conn.execute(
                """
                INSERT INTO api_tokens (id, workspace_id, user_id, name, token_hash, created_at, expires_at, scopes_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    replacement_id,
                    current["workspace_id"],
                    current["user_id"],
                    current["name"],
                    _hash_token(token),
                    created_at,
                    current["expires_at"],
                    json.dumps(scopes),
                ),
            )
            self.conn.execute(
                "DELETE FROM api_tokens WHERE id = ? AND workspace_id = ? AND user_id = ?",
                (token_id, workspace_id, token_owner_user_id),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "api_token.rotate",
                target_type="api_token",
                target_id=replacement_id,
                details={
                    "name": current["name"],
                    "rotated_from": token_id,
                    "expires_at": current["expires_at"],
                    "scopes": scopes,
                },
            )
        return {
            "id": replacement_id,
            "workspace_id": current["workspace_id"],
            "user_id": current["user_id"],
            "name": current["name"],
            "expires_at": current["expires_at"],
            "scopes": scopes,
            **_rotation_metadata(created_at, policy["rotation_due_in_days"]),
            "rotated_from": token_id,
            "token": token,
        }

    def record_audit_event(
        self,
        workspace_id: str | None,
        user_id: str,
        action: str,
        *,
        target_type: str,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        event_id = self._insert_audit_event(
            workspace_id,
            user_id,
            action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
        self._commit()
        return event_id

    def _insert_audit_event(
        self,
        workspace_id: str | None,
        user_id: str,
        action: str,
        *,
        target_type: str,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        if workspace_id:
            self._require_workspace(workspace_id)
        user_id = user_id.strip()
        action = action.strip()
        target_type = target_type.strip()
        if not user_id:
            raise ValueError("Audit user id is required.")
        if not action:
            raise ValueError("Audit action is required.")
        if not target_type:
            raise ValueError("Audit target type is required.")
        event_id = f"aud_{uuid.uuid4().hex}"
        created_at = _now()
        details_json = json.dumps(details or {}, sort_keys=True)
        previous_integrity_hash = self._latest_audit_integrity_hash(workspace_id)
        integrity_hash = _audit_integrity_hash(
            event_id=event_id,
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details_json=details_json,
            created_at=created_at,
            previous_integrity_hash=previous_integrity_hash,
        )
        self.conn.execute(
            """
            INSERT INTO audit_events (
              id, workspace_id, user_id, action, target_type, target_id, details_json,
              created_at, previous_integrity_hash, integrity_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                workspace_id,
                user_id,
                action,
                target_type,
                target_id,
                details_json,
                created_at,
                previous_integrity_hash,
                integrity_hash,
            ),
        )
        self._pending_audit_sink_events.append(
            {
                "id": event_id,
                "workspace_id": workspace_id,
                "user_id": user_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "details": json.loads(details_json),
                "created_at": created_at,
                "previous_integrity_hash": previous_integrity_hash,
                "integrity_hash": integrity_hash,
            }
        )
        return event_id

    def _latest_audit_integrity_hash(self, workspace_id: str | None) -> str | None:
        row = self._one(
            """
            SELECT integrity_hash
            FROM audit_events
            WHERE (workspace_id = ? OR (workspace_id IS NULL AND ? IS NULL))
              AND integrity_hash IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (workspace_id, workspace_id),
        )
        return row["integrity_hash"] if row else None

    def _flush_audit_sink_events(self) -> None:
        events = self._pending_audit_sink_events
        self._pending_audit_sink_events = []
        if not events:
            return
        writes: dict[Path, list[dict[str, Any]]] = {}
        seen_by_path: dict[Path, set[str]] = {}
        env_sink_path = _audit_sink_path(self.root)
        if env_sink_path:
            for event in events:
                self._queue_audit_sink_write(writes, seen_by_path, env_sink_path, event)
        workspace_sinks = self._workspace_audit_sink_paths(events)
        for event in events:
            workspace_id = event.get("workspace_id")
            if not isinstance(workspace_id, str):
                continue
            sink_path = workspace_sinks.get(workspace_id)
            if sink_path:
                self._queue_audit_sink_write(writes, seen_by_path, sink_path, event)
        for sink_path, sink_events in writes.items():
            self._write_audit_sink_events(sink_path, sink_events)

    def _workspace_audit_sink_paths(self, events: list[dict[str, Any]]) -> dict[str, Path]:
        workspace_ids = sorted(
            {
                event["workspace_id"]
                for event in events
                if isinstance(event.get("workspace_id"), str) and event.get("workspace_id")
            }
        )
        if not workspace_ids:
            return {}
        placeholders = ", ".join("?" for _ in workspace_ids)
        try:
            rows = self.conn.execute(
                f"""
                SELECT workspace_id, relative_path
                FROM workspace_audit_jsonl_sinks
                WHERE enabled = 1 AND workspace_id IN ({placeholders})
                """,
                tuple(workspace_ids),
            ).fetchall()
        except sqlite3.Error:
            return {}
        sinks: dict[str, Path] = {}
        for row in rows:
            sink_path = _workspace_audit_sink_path(self.root, row["relative_path"])
            if sink_path:
                sinks[row["workspace_id"]] = sink_path
        return sinks

    def _queue_audit_sink_write(
        self,
        writes: dict[Path, list[dict[str, Any]]],
        seen_by_path: dict[Path, set[str]],
        sink_path: Path,
        event: dict[str, Any],
    ) -> None:
        events = writes.setdefault(sink_path, [])
        seen = seen_by_path.setdefault(sink_path, set())
        event_id = event.get("id")
        if isinstance(event_id, str) and event_id in seen:
            return
        if isinstance(event_id, str):
            seen.add(event_id)
        events.append(event)

    def _write_audit_sink_events(self, sink_path: Path, events: list[dict[str, Any]]) -> None:
        try:
            sink_path.parent.mkdir(parents=True, exist_ok=True)
            with sink_path.open("a", encoding="utf-8") as sink:
                for event in events:
                    sink.write(json.dumps(_redact_audit_sink_event(event), sort_keys=True) + "\n")
        except OSError:
            return

    def list_audit_events(
        self,
        workspace_id: str,
        user_id: str,
        limit: int = 100,
        *,
        since: str | None = None,
        until: str | None = None,
        action: str | None = None,
        event_user_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.require_workspace_role(workspace_id, user_id, {"owner", "admin"})
        limit = max(1, min(int(limit), 500))
        since = _normalize_datetime_filter(since, "since")
        until = _normalize_datetime_filter(until, "until")
        if since and until and since > until:
            raise ValueError("since must be before until")
        action = action.strip() if action else None
        event_user_id = event_user_id.strip() if event_user_id else None
        target_type = target_type.strip() if target_type else None
        target_id = target_id.strip() if target_id else None
        where = ["workspace_id = ?"]
        args: list[Any] = [workspace_id]
        if since:
            where.append("created_at >= ?")
            args.append(since)
        if until:
            where.append("created_at <= ?")
            args.append(until)
        if action:
            where.append("action = ?")
            args.append(action)
        if event_user_id:
            where.append("user_id = ?")
            args.append(event_user_id)
        if target_type:
            where.append("target_type = ?")
            args.append(target_type)
        if target_id:
            where.append("target_id = ?")
            args.append(target_id)
        args.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM audit_events
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            args,
        )
        events = []
        for row in rows:
            event = dict(row)
            event["details"] = json.loads(event.pop("details_json"))
            events.append(event)
        return events

    def export_audit_events(
        self,
        workspace_id: str,
        user_id: str,
        limit: int = 500,
        *,
        since: str | None = None,
        until: str | None = None,
        action: str | None = None,
        event_user_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        format: str = "jsonl",
    ) -> str:
        events = self.list_audit_events(
            workspace_id,
            user_id,
            limit=limit,
            since=since,
            until=until,
            action=action,
            event_user_id=event_user_id,
            target_type=target_type,
            target_id=target_id,
        )
        ordered = list(reversed(events))
        export_format = format.strip().casefold()
        if export_format == "jsonl":
            return "\n".join(json.dumps(event, sort_keys=True) for event in ordered)
        if export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "id",
                    "workspace_id",
                    "user_id",
                    "action",
                    "target_type",
                    "target_id",
                    "created_at",
                    "details_json",
                    "previous_integrity_hash",
                    "integrity_hash",
                ]
            )
            for event in ordered:
                writer.writerow(
                    [
                        event["id"],
                        event["workspace_id"],
                        event["user_id"],
                        event["action"],
                        event["target_type"],
                        event["target_id"] or "",
                        event["created_at"],
                        json.dumps(event["details"], sort_keys=True),
                        event.get("previous_integrity_hash") or "",
                        event.get("integrity_hash") or "",
                    ]
            )
            return output.getvalue()
        raise ValueError("format must be jsonl or csv")

    def verify_audit_integrity(self, workspace_id: str, user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, user_id, WORKSPACE_ADMIN_ROLES)
        rows = self.conn.execute(
            """
            SELECT *
            FROM audit_events
            WHERE workspace_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (workspace_id,),
        )
        failures: list[dict[str, Any]] = []
        checked = 0
        legacy = 0
        expected_previous_hash: str | None = None
        latest_hash: str | None = None
        for row in rows:
            event = dict(row)
            stored_hash = event.get("integrity_hash")
            stored_previous = event.get("previous_integrity_hash")
            if not stored_hash:
                legacy += 1
                continue
            expected_hash = _audit_integrity_hash(
                event_id=event["id"],
                workspace_id=event["workspace_id"],
                user_id=event["user_id"],
                action=event["action"],
                target_type=event["target_type"],
                target_id=event["target_id"],
                details_json=event["details_json"],
                created_at=event["created_at"],
                previous_integrity_hash=stored_previous,
            )
            if stored_previous != expected_previous_hash:
                failures.append(
                    {
                        "id": event["id"],
                        "kind": "previous_hash_mismatch",
                        "expected": expected_previous_hash,
                        "actual": stored_previous,
                    }
                )
            if stored_hash != expected_hash:
                failures.append(
                    {
                        "id": event["id"],
                        "kind": "integrity_hash_mismatch",
                        "expected": expected_hash,
                        "actual": stored_hash,
                    }
                )
            checked += 1
            expected_previous_hash = stored_hash
            latest_hash = stored_hash
        return {
            "workspace_id": workspace_id,
            "ok": not failures,
            "checked": checked,
            "legacy": legacy,
            "failure_count": len(failures),
            "failures": failures[:20],
            "latest_integrity_hash": latest_hash,
        }

    def export_workspace_bundle(
        self,
        workspace_id: str,
        actor_user_id: str,
        output_path: str | Path,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        output = Path(output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        workspace = dict(self._one("SELECT id, name, created_at FROM workspaces WHERE id = ?", (workspace_id,)))
        documents = _rows(self.conn.execute(
            """
            SELECT id, workspace_id, folder_id, name, description, kind,
                   access_mode, page_count, line_count, created_at, updated_at
            FROM documents
            WHERE workspace_id = ?
            ORDER BY created_at, id
            """,
            (workspace_id,),
        ))
        exports: dict[str, list[dict[str, Any]]] = {
            "workspace.jsonl": [workspace],
            "workspace_members.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT workspace_id, user_id, role, created_at
                    FROM workspace_members
                    WHERE workspace_id = ?
                    ORDER BY user_id
                    """,
                    (workspace_id,),
                )
            ),
            "workspace_invitations.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT id, workspace_id, email, role, invited_by, status, created_at,
                           expires_at, accepted_by, accepted_at, revoked_at
                    FROM workspace_invitations
                    WHERE workspace_id = ?
                    ORDER BY created_at, id
                    """,
                    (workspace_id,),
                )
            ),
            "workspace_groups.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT id, workspace_id, name, created_at
                    FROM workspace_groups
                    WHERE workspace_id = ?
                    ORDER BY name, id
                    """,
                    (workspace_id,),
                )
            ),
            "workspace_group_members.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT group_id, workspace_id, user_id, created_at
                    FROM workspace_group_members
                    WHERE workspace_id = ?
                    ORDER BY group_id, user_id
                    """,
                    (workspace_id,),
                )
            ),
            "folders.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT id, workspace_id, parent_id, name, path, created_at
                    FROM folders
                    WHERE workspace_id = ?
                    ORDER BY path
                    """,
                    (workspace_id,),
                )
            ),
            "folder_access_grants.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT folder_id, workspace_id, user_id, role, granted_by, created_at
                    FROM folder_access_grants
                    WHERE workspace_id = ?
                    ORDER BY folder_id, user_id
                    """,
                    (workspace_id,),
                )
            ),
            "folder_group_access_grants.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT folder_id, workspace_id, group_id, role, granted_by, created_at
                    FROM folder_group_access_grants
                    WHERE workspace_id = ?
                    ORDER BY folder_id, group_id
                    """,
                    (workspace_id,),
                )
            ),
            "documents.jsonl": documents,
            "document_access_grants.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT doc_id, workspace_id, user_id, role, granted_by, created_at
                    FROM document_access_grants
                    WHERE workspace_id = ?
                    ORDER BY doc_id, user_id
                    """,
                    (workspace_id,),
                )
            ),
            "document_group_access_grants.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT doc_id, workspace_id, group_id, role, granted_by, created_at
                    FROM document_group_access_grants
                    WHERE workspace_id = ?
                    ORDER BY doc_id, group_id
                    """,
                    (workspace_id,),
                )
            ),
            "query_source_sets.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT id, workspace_id, name, description, shared, created_by, created_at, updated_at
                    FROM query_source_sets
                    WHERE workspace_id = ?
                    ORDER BY updated_at, id
                    """,
                    (workspace_id,),
                )
            ),
            "query_source_set_documents.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT source_set_id, workspace_id, doc_id, position
                    FROM query_source_set_documents
                    WHERE workspace_id = ?
                    ORDER BY source_set_id, position, doc_id
                    """,
                    (workspace_id,),
                )
            ),
            "document_pages.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT p.doc_id, p.page, p.content
                    FROM document_pages p
                    JOIN documents d ON d.id = p.doc_id
                    WHERE d.workspace_id = ?
                    ORDER BY p.doc_id, p.page
                    """,
                    (workspace_id,),
                )
            ),
            "document_versions.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT id, doc_id, workspace_id, version, action, actor_user_id,
                           name, kind, source_name, page_count, line_count, created_at
                    FROM document_versions
                    WHERE workspace_id = ?
                    ORDER BY doc_id, version
                    """,
                    (workspace_id,),
                )
            ),
            "conversations.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT id, workspace_id, created_by, title, auto_title_pending,
                           source_set_id, folder_id, created_at, updated_at, archived_at
                    FROM conversations
                    WHERE workspace_id = ?
                    ORDER BY created_at, id
                    """,
                    (workspace_id,),
                )
            ),
            "conversation_messages.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT id, conversation_id, workspace_id, user_id, role, content, run_id, created_at
                    FROM conversation_messages
                    WHERE workspace_id = ?
                    ORDER BY conversation_id, created_at, id
                    """,
                    (workspace_id,),
                )
            ),
            "query_runs.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT id, workspace_id, actor_user_id, query, scope_json, created_at, completed_at
                    FROM query_runs
                    WHERE workspace_id = ?
                    ORDER BY created_at, id
                    """,
                    (workspace_id,),
                )
            ),
            "evidence.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT e.id, e.run_id, e.doc_id, e.node_id, e.page_start, e.page_end,
                           e.line_start, e.line_end, e.text, e.reason, e.score, e.created_at
                    FROM evidence e
                    JOIN query_runs q ON q.id = e.run_id
                    WHERE q.workspace_id = ?
                    ORDER BY e.run_id, e.created_at, e.id
                    """,
                    (workspace_id,),
                )
            ),
            "citations.jsonl": _rows(
                self.conn.execute(
                    """
                    SELECT c.id, c.run_id, c.evidence_id, c.doc_id, c.label,
                           c.page_start, c.page_end, c.line_start, c.line_end, c.created_at
                    FROM citations c
                    JOIN query_runs q ON q.id = c.run_id
                    WHERE q.workspace_id = ?
                    ORDER BY c.run_id, c.created_at, c.id
                    """,
                    (workspace_id,),
                )
            ),
            "virtual_nodes.jsonl": self.list_virtual_nodes(workspace_id=workspace_id),
            "api_token_policy.jsonl": [self._api_token_policy(workspace_id)],
            "query_retention_policy.jsonl": [self._query_retention_policy(workspace_id)],
            "audit_retention_policy.jsonl": [self._audit_retention_policy(workspace_id)],
            "workspace_quota_policy.jsonl": [self._workspace_quota_policy(workspace_id)],
            "provider_config.jsonl": [self._workspace_provider_config_metadata(workspace_id)],
            "audit_events.jsonl": _workspace_audit_export_rows(self.conn, workspace_id),
        }
        manifest = {
            "format": WORKSPACE_EXPORT_FORMAT,
            "workspace_id": workspace_id,
            "exported_at": _now(),
            "artifact": output.name,
            "tables": {name.removesuffix(".jsonl"): len(rows) for name, rows in exports.items()},
            "omitted": list(WORKSPACE_EXPORT_OMITTED_POLICIES),
        }
        export_payloads = {name: _jsonl(rows) for name, rows in exports.items()}
        manifest["checksums"] = {
            name: _sha256_bytes(payload.encode("utf-8"))
            for name, payload in sorted(export_payloads.items())
        }
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            for name, payload in export_payloads.items():
                archive.writestr(name, payload)
        with self._atomic():
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "workspace.export",
                target_type="workspace",
                target_id=workspace_id,
                details={
                    "artifact": output.name,
                    "format": manifest["format"],
                    "tables": manifest["tables"],
                },
            )
        return manifest

    def validate_workspace_import_bundle(self, bundle_path: str | Path) -> dict[str, Any]:
        return validate_workspace_import_bundle(bundle_path)

    def import_workspace_bundle(self, bundle_path: str | Path) -> dict[str, Any]:
        validation = validate_workspace_import_bundle(bundle_path)
        if not validation["ok"]:
            raise ValueError("workspace import bundle is invalid: " + "; ".join(validation["errors"]))
        workspace_id = validation["workspace_id"]
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            raise ValueError("workspace import bundle is missing a workspace id")
        workspace_id = workspace_id.strip()
        if self._one("SELECT id FROM workspaces WHERE id = ?", (workspace_id,)):
            raise ValueError(f"Workspace already exists: {workspace_id}")
        bundle = Path(bundle_path).expanduser()
        errors: list[str] = []
        rows_by_table: dict[str, list[dict[str, Any]]] = {}
        with zipfile.ZipFile(bundle) as archive:
            names = set(archive.namelist())
            for table in WORKSPACE_EXPORT_TABLES:
                filename = f"{table}.jsonl"
                if filename not in names and table in WORKSPACE_EXPORT_OPTIONAL_TABLES:
                    rows = []
                else:
                    rows = _read_workspace_import_jsonl(archive, filename, errors)
                rows_by_table[table] = _workspace_import_rows_for_insert(table, rows)
        if errors:
            raise ValueError("workspace import bundle is invalid: " + "; ".join(errors))
        workspace_rows = rows_by_table.get("workspace", [])
        if len(workspace_rows) != 1 or workspace_rows[0].get("id") != workspace_id:
            raise ValueError("workspace import bundle workspace row does not match manifest")
        inserted: dict[str, int] = {}
        try:
            with self._atomic():
                for table in WORKSPACE_IMPORT_INSERT_ORDER:
                    rows = rows_by_table.get(table, [])
                    if table == "virtual_nodes":
                        rows = sorted(rows, key=lambda row: (str(row.get("path", "")).count("/"), str(row.get("path", ""))))
                    db_table = WORKSPACE_IMPORT_DB_TABLES.get(table, table)
                    inserted[table] = self._insert_workspace_import_rows(db_table, rows)
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"workspace import failed integrity checks: {exc}") from exc
        self.rebuild_virtual_index()
        return {
            "ok": True,
            "workspace_id": workspace_id,
            "artifact": validation["artifact"],
            "table_counts": validation["table_counts"],
            "inserted": inserted,
            "omitted": list(WORKSPACE_EXPORT_OMITTED_POLICIES),
            "warnings": validation["warnings"],
        }

    def _insert_workspace_import_rows(self, db_table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        columns = [row["name"] for row in self.conn.execute(f"PRAGMA table_info({db_table})")]
        inserted = 0
        for row in rows:
            values = {column: row[column] for column in columns if column in row}
            if not values:
                continue
            names = list(values)
            placeholders = ", ".join("?" for _ in names)
            self.conn.execute(
                f"INSERT INTO {db_table} ({', '.join(names)}) VALUES ({placeholders})",
                tuple(values[name] for name in names),
            )
            inserted += 1
        return inserted

    def _query_retention_policy(self, workspace_id: str) -> dict[str, Any]:
        self._require_workspace(workspace_id)
        row = self._one(
            """
            SELECT workspace_id, retention_days, legal_hold, legal_hold_reason, updated_at, updated_by
            FROM query_retention_policies
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )
        if not row:
            return {
                "workspace_id": workspace_id,
                "retention_days": None,
                "legal_hold": False,
                "legal_hold_reason": None,
                "updated_at": None,
                "updated_by": None,
            }
        policy = dict(row)
        policy["legal_hold"] = bool(policy.get("legal_hold"))
        return policy

    def get_query_retention_policy(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        return self._query_retention_policy(workspace_id)

    def set_query_retention_policy(
        self,
        workspace_id: str,
        actor_user_id: str,
        *,
        retention_days: int | None | object = _UNSET,
        legal_hold: bool | object = _UNSET,
        legal_hold_reason: str | None | object = _UNSET,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        if retention_days is _UNSET and legal_hold is _UNSET and legal_hold_reason is _UNSET:
            raise ValueError("choose retention_days, legal_hold, or legal_hold_reason")
        current = self._query_retention_policy(workspace_id)
        next_retention_days = (
            current["retention_days"]
            if retention_days is _UNSET
            else _normalize_policy_days(retention_days, "retention_days")
        )
        if legal_hold is _UNSET:
            next_legal_hold = bool(current["legal_hold"])
        else:
            if not isinstance(legal_hold, bool):
                raise ValueError("legal_hold must be a boolean")
            next_legal_hold = legal_hold
        if legal_hold_reason is _UNSET:
            next_legal_hold_reason = current["legal_hold_reason"] if next_legal_hold else None
        else:
            next_legal_hold_reason = _normalize_legal_hold_reason(legal_hold_reason)
        if next_legal_hold_reason and not next_legal_hold:
            raise ValueError("legal_hold_reason requires legal_hold")
        if not next_legal_hold:
            next_legal_hold_reason = None
        updated_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO query_retention_policies (
                  workspace_id, retention_days, legal_hold, legal_hold_reason, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                  retention_days = excluded.retention_days,
                  legal_hold = excluded.legal_hold,
                  legal_hold_reason = excluded.legal_hold_reason,
                  updated_at = excluded.updated_at,
                  updated_by = excluded.updated_by
                """,
                (
                    workspace_id,
                    next_retention_days,
                    int(next_legal_hold),
                    next_legal_hold_reason,
                    updated_at,
                    actor_user_id.strip(),
                ),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "query.retention_policy_update",
                target_type="query_retention_policy",
                target_id=workspace_id,
                details={
                    "retention_days": next_retention_days,
                    "legal_hold": next_legal_hold,
                    "legal_hold_reason": next_legal_hold_reason,
                },
            )
        return self._query_retention_policy(workspace_id)

    def purge_query_runs_by_retention(self, workspace_id: str, actor_user_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        policy = self._query_retention_policy(workspace_id)
        retention_days = policy["retention_days"]
        if retention_days is None:
            raise ValueError("query retention policy is not set")
        cutoff = (_now_dt() - timedelta(days=retention_days)).isoformat()
        if dry_run:
            matched = int(
                self.conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM query_runs
                    WHERE workspace_id = ? AND created_at < ?
                    """,
                    (workspace_id, cutoff),
                ).fetchone()["count"]
            )
            return {
                "workspace_id": workspace_id,
                "retention_days": retention_days,
                "cutoff": cutoff,
                "matched": matched,
                "purged": 0,
                "dry_run": True,
                "legal_hold": bool(policy["legal_hold"]),
                "legal_hold_reason": policy["legal_hold_reason"],
            }
        if policy["legal_hold"]:
            raise ValueError("query retention legal hold is enabled")
        with self._atomic():
            deleted = self.conn.execute(
                """
                DELETE FROM query_runs
                WHERE workspace_id = ? AND created_at < ?
                """,
                (workspace_id, cutoff),
            )
            purged = max(0, deleted.rowcount)
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "query.retention_purge",
                target_type="query_retention_policy",
                target_id=workspace_id,
                details={
                    "retention_days": retention_days,
                    "cutoff": cutoff,
                    "purged": purged,
                },
            )
        return {
            "workspace_id": workspace_id,
            "retention_days": retention_days,
            "cutoff": cutoff,
            "matched": purged,
            "purged": purged,
            "dry_run": False,
            "legal_hold": False,
            "legal_hold_reason": None,
        }

    def _audit_retention_policy(self, workspace_id: str) -> dict[str, Any]:
        self._require_workspace(workspace_id)
        row = self._one(
            """
            SELECT workspace_id, retention_days, legal_hold, legal_hold_reason, updated_at, updated_by
            FROM audit_retention_policies
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        )
        if not row:
            return {
                "workspace_id": workspace_id,
                "retention_days": None,
                "legal_hold": False,
                "legal_hold_reason": None,
                "updated_at": None,
                "updated_by": None,
            }
        policy = dict(row)
        policy["legal_hold"] = bool(policy.get("legal_hold"))
        return policy

    def get_audit_retention_policy(self, workspace_id: str, actor_user_id: str) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        return self._audit_retention_policy(workspace_id)

    def set_audit_retention_policy(
        self,
        workspace_id: str,
        actor_user_id: str,
        *,
        retention_days: int | None | object = _UNSET,
        legal_hold: bool | object = _UNSET,
        legal_hold_reason: str | None | object = _UNSET,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        if retention_days is _UNSET and legal_hold is _UNSET and legal_hold_reason is _UNSET:
            raise ValueError("choose retention_days, legal_hold, or legal_hold_reason")
        current = self._audit_retention_policy(workspace_id)
        next_retention_days = (
            current["retention_days"]
            if retention_days is _UNSET
            else _normalize_policy_days(retention_days, "retention_days")
        )
        if legal_hold is _UNSET:
            next_legal_hold = bool(current["legal_hold"])
        else:
            if not isinstance(legal_hold, bool):
                raise ValueError("legal_hold must be a boolean")
            next_legal_hold = legal_hold
        if legal_hold_reason is _UNSET:
            next_legal_hold_reason = current["legal_hold_reason"] if next_legal_hold else None
        else:
            next_legal_hold_reason = _normalize_legal_hold_reason(legal_hold_reason)
        if next_legal_hold_reason and not next_legal_hold:
            raise ValueError("legal_hold_reason requires legal_hold")
        if not next_legal_hold:
            next_legal_hold_reason = None
        updated_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO audit_retention_policies (
                  workspace_id, retention_days, legal_hold, legal_hold_reason, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                  retention_days = excluded.retention_days,
                  legal_hold = excluded.legal_hold,
                  legal_hold_reason = excluded.legal_hold_reason,
                  updated_at = excluded.updated_at,
                  updated_by = excluded.updated_by
                """,
                (
                    workspace_id,
                    next_retention_days,
                    int(next_legal_hold),
                    next_legal_hold_reason,
                    updated_at,
                    actor_user_id.strip(),
                ),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "audit.retention_policy_update",
                target_type="audit_retention_policy",
                target_id=workspace_id,
                details={
                    "retention_days": next_retention_days,
                    "legal_hold": next_legal_hold,
                    "legal_hold_reason": next_legal_hold_reason,
                },
            )
        return self._audit_retention_policy(workspace_id)

    def purge_audit_events_by_retention(self, workspace_id: str, actor_user_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        policy = self._audit_retention_policy(workspace_id)
        retention_days = policy["retention_days"]
        if retention_days is None:
            raise ValueError("audit retention policy is not set")
        cutoff = (_now_dt() - timedelta(days=retention_days)).isoformat()
        if dry_run:
            matched = int(
                self.conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM audit_events
                    WHERE workspace_id = ? AND created_at < ?
                    """,
                    (workspace_id, cutoff),
                ).fetchone()["count"]
            )
            return {
                "workspace_id": workspace_id,
                "retention_days": retention_days,
                "cutoff": cutoff,
                "matched": matched,
                "purged": 0,
                "dry_run": True,
                "legal_hold": bool(policy["legal_hold"]),
                "legal_hold_reason": policy["legal_hold_reason"],
            }
        if policy["legal_hold"]:
            raise ValueError("audit retention legal hold is enabled")
        with self._atomic():
            deleted = self.conn.execute(
                """
                DELETE FROM audit_events
                WHERE workspace_id = ? AND created_at < ?
                """,
                (workspace_id, cutoff),
            )
            purged = max(0, deleted.rowcount)
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "audit.retention_purge",
                target_type="audit_retention_policy",
                target_id=workspace_id,
                details={
                    "retention_days": retention_days,
                    "cutoff": cutoff,
                    "purged": purged,
                },
            )
        result = {
            "workspace_id": workspace_id,
            "retention_days": retention_days,
            "cutoff": cutoff,
            "matched": purged,
            "purged": purged,
            "dry_run": False,
            "legal_hold": False,
            "legal_hold_reason": None,
        }
        return result

    def _conversation_for_actor(
        self,
        conversation_id: str,
        actor_user_id: str,
        *,
        expected_workspace_id: str | None = None,
        allow_archived: bool = False,
    ) -> dict[str, Any]:
        actor_user_id = actor_user_id.strip()
        conversation_id = conversation_id.strip()
        if not conversation_id:
            raise ValueError("Conversation id is required.")
        row = self._one("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
        if not row:
            raise ValueError(f"Conversation not found: {conversation_id}")
        conversation = dict(row)
        if expected_workspace_id and conversation["workspace_id"] != expected_workspace_id:
            raise PermissionError("conversation access denied")
        self.require_workspace_access(conversation["workspace_id"], actor_user_id)
        if conversation["created_by"] != actor_user_id:
            raise PermissionError("conversation access denied")
        if conversation.get("archived_at") and not allow_archived:
            raise PermissionError("conversation archived")
        return self._conversation_with_visible_scope(conversation, actor_user_id)

    def _conversation_with_visible_scope(self, conversation: dict[str, Any], actor_user_id: str) -> dict[str, Any]:
        source_set_id = conversation.get("source_set_id")
        if source_set_id:
            source_set = self._query_source_set_row(conversation["workspace_id"], source_set_id)
            if source_set is None or not self._can_use_query_source_set(
                conversation["workspace_id"],
                actor_user_id,
                source_set,
            ):
                conversation = {**conversation, "source_set_id": None}
        return conversation

    def _require_workspace(self, workspace_id: str | None) -> None:
        if workspace_id and self._one("SELECT id FROM workspaces WHERE id = ?", (workspace_id,)):
            return
        raise ValueError(f"Workspace not found: {workspace_id}")

    def create_folder(
        self,
        name: str,
        parent_id: str | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> str:
        name = name.strip()
        if not name or "/" in name:
            raise ValueError("Folder name must be non-empty and must not contain '/'.")
        folder_id = f"fld_{uuid.uuid4().hex}"
        parent_path = ""
        if parent_id:
            parent = self._one("SELECT path, workspace_id FROM folders WHERE id = ?", (parent_id,))
            if not parent:
                raise ValueError(f"Parent folder not found: {parent_id}")
            if workspace_id and parent["workspace_id"] != workspace_id:
                raise PermissionError("folder access denied")
            workspace_id = workspace_id or parent["workspace_id"]
            parent_path = parent["path"]
        self.require_workspace_write(workspace_id, actor_user_id)
        path = f"{parent_path}/{name}" if parent_path else f"/{name}"
        existing = self._one(
            """
            SELECT id
            FROM folders
            WHERE path = ? AND (workspace_id = ? OR (workspace_id IS NULL AND ? IS NULL))
            """,
            (path, workspace_id, workspace_id),
        )
        if existing:
            raise ValueError("Folder path already exists in this workspace.")
        try:
            self.conn.execute(
                "INSERT INTO folders (id, workspace_id, parent_id, name, path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (folder_id, workspace_id, parent_id, name, path, _now()),
            )
            self._commit()
        except sqlite3.IntegrityError as exc:
            self.conn.rollback()
            message = str(exc).casefold()
            if "folders" in message and "path" in message:
                raise ValueError("Folder path already exists in this workspace.") from exc
            raise
        return folder_id

    def list_folders(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        if workspace_id:
            rows = self.conn.execute("SELECT * FROM folders WHERE workspace_id = ? ORDER BY path", (workspace_id,))
        else:
            rows = self.conn.execute("SELECT * FROM folders ORDER BY path")
        return [dict(row) for row in rows]

    def rename_folder(
        self,
        folder_id: str,
        name: str,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        folder_id = folder_id.strip()
        name = name.strip()
        if not folder_id:
            raise ValueError("Folder id is required.")
        if not name or "/" in name:
            raise ValueError("Folder name must be non-empty and must not contain '/'.")
        folder = self._one("SELECT * FROM folders WHERE id = ?", (folder_id,))
        if not folder:
            return None
        if workspace_id and folder["workspace_id"] != workspace_id:
            return None
        folder_workspace_id = folder["workspace_id"]
        self.require_workspace_write(folder_workspace_id, actor_user_id)
        parent_path = ""
        if folder["parent_id"]:
            parent = self._one("SELECT path, workspace_id FROM folders WHERE id = ?", (folder["parent_id"],))
            if not parent:
                raise ValueError(f"Parent folder not found: {folder['parent_id']}")
            if parent["workspace_id"] != folder_workspace_id:
                raise PermissionError("folder access denied")
            parent_path = parent["path"]
        old_path = folder["path"]
        new_path = f"{parent_path}/{name}" if parent_path else f"/{name}"
        existing = self._one(
            """
            SELECT id
            FROM folders
            WHERE id != ?
              AND path = ?
              AND (workspace_id = ? OR (workspace_id IS NULL AND ? IS NULL))
            """,
            (folder_id, new_path, folder_workspace_id, folder_workspace_id),
        )
        if existing:
            raise ValueError("Folder path already exists in this workspace.")
        if folder_workspace_id:
            rows = self.conn.execute("SELECT id, path FROM folders WHERE workspace_id = ?", (folder_workspace_id,))
        else:
            rows = self.conn.execute("SELECT id, path FROM folders WHERE workspace_id IS NULL")
        descendants = sorted(
            [dict(row) for row in rows if row["path"].startswith(f"{old_path}/")],
            key=lambda row: len(row["path"]),
        )
        try:
            with self._atomic():
                self.conn.execute(
                    "UPDATE folders SET name = ?, path = ? WHERE id = ?",
                    (name, new_path, folder_id),
                )
                for descendant in descendants:
                    suffix = descendant["path"][len(old_path) :]
                    self.conn.execute(
                        "UPDATE folders SET path = ? WHERE id = ?",
                        (f"{new_path}{suffix}", descendant["id"]),
                    )
                if actor_user_id and folder_workspace_id:
                    self._insert_audit_event(
                        folder_workspace_id,
                        actor_user_id,
                        "folder.rename",
                        target_type="folder",
                        target_id=folder_id,
                        details={"name": name, "previous_path": old_path, "path": new_path},
                    )
        except sqlite3.IntegrityError as exc:
            message = str(exc).casefold()
            if "folders" in message and "path" in message:
                raise ValueError("Folder path already exists in this workspace.") from exc
            raise
        renamed = self._one("SELECT * FROM folders WHERE id = ?", (folder_id,))
        return dict(renamed) if renamed else None

    def move_folder(
        self,
        folder_id: str,
        parent_id: str | None = None,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        folder_id = folder_id.strip()
        parent_id = parent_id.strip() if parent_id else None
        if not folder_id:
            raise ValueError("Folder id is required.")
        folder = self._one("SELECT * FROM folders WHERE id = ?", (folder_id,))
        if not folder:
            return None
        if workspace_id and folder["workspace_id"] != workspace_id:
            return None
        folder_workspace_id = folder["workspace_id"]
        self.require_workspace_write(folder_workspace_id, actor_user_id)
        old_path = folder["path"]
        parent_path = ""
        if parent_id:
            parent = self._one("SELECT * FROM folders WHERE id = ?", (parent_id,))
            if not parent:
                raise ValueError(f"Parent folder not found: {parent_id}")
            if parent["workspace_id"] != folder_workspace_id:
                raise PermissionError("folder access denied")
            if parent["id"] == folder_id or parent["path"].startswith(f"{old_path}/"):
                raise ValueError("Folder cannot be moved under itself.")
            parent_path = parent["path"]
        if parent_id == folder["parent_id"]:
            return dict(folder)
        new_path = f"{parent_path}/{folder['name']}" if parent_path else f"/{folder['name']}"
        existing = self._one(
            """
            SELECT id
            FROM folders
            WHERE id != ?
              AND path = ?
              AND (workspace_id = ? OR (workspace_id IS NULL AND ? IS NULL))
            """,
            (folder_id, new_path, folder_workspace_id, folder_workspace_id),
        )
        if existing:
            raise ValueError("Folder path already exists in this workspace.")
        if folder_workspace_id:
            rows = self.conn.execute("SELECT id, path FROM folders WHERE workspace_id = ?", (folder_workspace_id,))
        else:
            rows = self.conn.execute("SELECT id, path FROM folders WHERE workspace_id IS NULL")
        descendants = sorted(
            [dict(row) for row in rows if row["path"].startswith(f"{old_path}/")],
            key=lambda row: len(row["path"]),
        )
        try:
            with self._atomic():
                self.conn.execute(
                    "UPDATE folders SET parent_id = ?, path = ? WHERE id = ?",
                    (parent_id, new_path, folder_id),
                )
                for descendant in descendants:
                    suffix = descendant["path"][len(old_path) :]
                    self.conn.execute(
                        "UPDATE folders SET path = ? WHERE id = ?",
                        (f"{new_path}{suffix}", descendant["id"]),
                    )
                if actor_user_id and folder_workspace_id:
                    self._insert_audit_event(
                        folder_workspace_id,
                        actor_user_id,
                        "folder.move",
                        target_type="folder",
                        target_id=folder_id,
                        details={
                            "previous_parent_id": folder["parent_id"],
                            "parent_id": parent_id,
                            "previous_path": old_path,
                            "path": new_path,
                        },
                    )
        except sqlite3.IntegrityError as exc:
            message = str(exc).casefold()
            if "folders" in message and "path" in message:
                raise ValueError("Folder path already exists in this workspace.") from exc
            raise
        moved = self._one("SELECT * FROM folders WHERE id = ?", (folder_id,))
        return dict(moved) if moved else None

    def delete_folder(
        self,
        folder_id: str,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> bool:
        folder_id = folder_id.strip()
        if not folder_id:
            raise ValueError("Folder id is required.")
        folder = self._one("SELECT * FROM folders WHERE id = ?", (folder_id,))
        if not folder:
            return False
        if workspace_id and folder["workspace_id"] != workspace_id:
            return False
        folder_workspace_id = folder["workspace_id"]
        self.require_workspace_write(folder_workspace_id, actor_user_id)
        with self._atomic():
            cursor = self.conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
            deleted = cursor.rowcount > 0
            if deleted and actor_user_id and folder_workspace_id:
                self._insert_audit_event(
                    folder_workspace_id,
                    actor_user_id,
                    "folder.delete",
                    target_type="folder",
                    target_id=folder_id,
                    details={"name": folder["name"], "path": folder["path"]},
                )
        return deleted

    def list_folder_access(
        self,
        folder_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
    ) -> dict[str, Any] | None:
        folder = self._one("SELECT * FROM folders WHERE id = ?", (folder_id.strip(),))
        if not folder or folder["workspace_id"] != workspace_id:
            return None
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        rows = self.conn.execute(
            """
            SELECT folder_id, workspace_id, user_id, role, granted_by, created_at
            FROM folder_access_grants
            WHERE folder_id = ?
            ORDER BY user_id
            """,
            (folder["id"],),
        )
        group_rows = self.conn.execute(
            """
            SELECT fg.folder_id, fg.workspace_id, fg.group_id, g.name AS group_name,
                   fg.role, fg.granted_by, fg.created_at
            FROM folder_group_access_grants fg
            JOIN workspace_groups g ON g.id = fg.group_id
            WHERE fg.folder_id = ?
            ORDER BY g.name, fg.group_id
            """,
            (folder["id"],),
        )
        return {
            "folder": dict(folder),
            "workspace_id": workspace_id,
            "grants": [dict(row) for row in rows],
            "group_grants": [dict(row) for row in group_rows],
        }

    def grant_folder_access(
        self,
        folder_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        folder = self._one("SELECT * FROM folders WHERE id = ?", (folder_id.strip(),))
        if not folder or folder["workspace_id"] != workspace_id:
            return None
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        user_id = user_id.strip()
        if not user_id:
            raise ValueError("User id is required.")
        self.require_workspace_access(workspace_id, user_id)
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO folder_access_grants (folder_id, workspace_id, user_id, role, granted_by, created_at)
                VALUES (?, ?, ?, 'read', ?, ?)
                ON CONFLICT(folder_id, user_id) DO UPDATE SET
                  role = excluded.role,
                  granted_by = excluded.granted_by,
                  created_at = excluded.created_at
                """,
                (folder["id"], workspace_id, user_id, actor_user_id, now),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "folder.access_grant",
                target_type="folder",
                target_id=folder["id"],
                details={"user_id": user_id, "role": "read", "path": folder["path"]},
            )
        return self.list_folder_access(folder["id"], workspace_id=workspace_id, actor_user_id=actor_user_id)

    def grant_folder_group_access(
        self,
        folder_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        group_id: str,
    ) -> dict[str, Any] | None:
        folder = self._one("SELECT * FROM folders WHERE id = ?", (folder_id.strip(),))
        if not folder or folder["workspace_id"] != workspace_id:
            return None
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._require_workspace_group(workspace_id, group_id)
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO folder_group_access_grants (folder_id, workspace_id, group_id, role, granted_by, created_at)
                VALUES (?, ?, ?, 'read', ?, ?)
                ON CONFLICT(folder_id, group_id) DO UPDATE SET
                  role = excluded.role,
                  granted_by = excluded.granted_by,
                  created_at = excluded.created_at
                """,
                (folder["id"], workspace_id, group["id"], actor_user_id, now),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "folder.group_access_grant",
                target_type="folder",
                target_id=folder["id"],
                details={"group_id": group["id"], "group_name": group["name"], "role": "read", "path": folder["path"]},
            )
        return self.list_folder_access(folder["id"], workspace_id=workspace_id, actor_user_id=actor_user_id)

    def revoke_folder_access(
        self,
        folder_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        user_id: str,
    ) -> bool:
        folder = self._one("SELECT * FROM folders WHERE id = ?", (folder_id.strip(),))
        if not folder or folder["workspace_id"] != workspace_id:
            return False
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        user_id = user_id.strip()
        if not user_id:
            raise ValueError("User id is required.")
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM folder_access_grants WHERE folder_id = ? AND user_id = ?",
                (folder["id"], user_id),
            )
            revoked = cursor.rowcount > 0
            if revoked:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "folder.access_revoke",
                    target_type="folder",
                    target_id=folder["id"],
                    details={"user_id": user_id, "role": "read", "path": folder["path"]},
                )
        return revoked

    def revoke_folder_group_access(
        self,
        folder_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        group_id: str,
    ) -> bool:
        folder = self._one("SELECT * FROM folders WHERE id = ?", (folder_id.strip(),))
        if not folder or folder["workspace_id"] != workspace_id:
            return False
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._require_workspace_group(workspace_id, group_id)
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM folder_group_access_grants WHERE folder_id = ? AND group_id = ?",
                (folder["id"], group["id"]),
            )
            revoked = cursor.rowcount > 0
            if revoked:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "folder.group_access_revoke",
                    target_type="folder",
                    target_id=folder["id"],
                    details={"group_id": group["id"], "group_name": group["name"], "path": folder["path"]},
                )
        return revoked

    def register_document(
        self,
        *,
        doc_id: str | None = None,
        name: str,
        source_path: str,
        kind: str,
        description: str = "",
        folder_id: str | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        page_count: int | None = None,
        line_count: int | None = None,
    ) -> str:
        if folder_id:
            folder = self._one("SELECT id, workspace_id FROM folders WHERE id = ?", (folder_id,))
            if not folder:
                raise ValueError(f"Folder not found: {folder_id}")
            if workspace_id and folder["workspace_id"] != workspace_id:
                raise PermissionError("folder access denied")
            workspace_id = workspace_id or folder["workspace_id"]
        self.require_workspace_write(workspace_id, actor_user_id)
        if not name.strip():
            raise ValueError("Document name is required.")
        if kind not in {"pdf", "md", "markdown", "txt", "unknown"}:
            raise ValueError(f"Unsupported document kind: {kind}")
        doc_id = doc_id or f"doc_{uuid.uuid4().hex}"
        if "/" in doc_id or "%" in doc_id:
            raise ValueError("doc_id must be URL-safe")
        existing = self.get_document(doc_id)
        if existing and existing["workspace_id"] and existing["workspace_id"] != workspace_id:
            raise ValueError("Document belongs to another workspace.")
        if workspace_id and (not existing or not existing.get("workspace_id")):
            self._enforce_workspace_quota(workspace_id, documents_delta=1)
        now = _now()
        self.conn.execute(
            """
            INSERT INTO documents (
              id, workspace_id, folder_id, name, description, source_path, kind,
              page_count, line_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              workspace_id = excluded.workspace_id,
              folder_id = excluded.folder_id,
              name = excluded.name,
              description = excluded.description,
              source_path = excluded.source_path,
              kind = excluded.kind,
              page_count = excluded.page_count,
              line_count = excluded.line_count,
              updated_at = excluded.updated_at
            """,
            (
                doc_id,
                workspace_id,
                folder_id,
                name.strip(),
                description.strip(),
                str(Path(source_path).expanduser()),
                kind,
                page_count,
                line_count,
                now,
                now,
            ),
        )
        self._commit()
        return doc_id

    def ingest_file(
        self,
        file_path: str | Path,
        *,
        folder_id: str | None = None,
        doc_id: str | None = None,
        name: str | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        audit_action: str = "document.ingest",
        audit_details: dict[str, Any] | None = None,
    ) -> str:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        self.require_workspace_write(workspace_id, actor_user_id)
        pages = _extract_pages(path)
        kind = _kind_for(path)
        existing_doc_id = doc_id.strip() if doc_id else None
        existing = self.get_document(existing_doc_id) if existing_doc_id else None
        if existing and existing["workspace_id"] and existing["workspace_id"] != workspace_id:
            raise ValueError("Document belongs to another workspace.")
        if existing:
            self._require_document_write(existing, actor_user_id)
        with self._atomic():
            if existing:
                self._purge_document_index(existing["id"])
            version_action = audit_action
            doc_id = self.register_document(
                doc_id=doc_id,
                name=name or path.name,
                source_path=str(path),
                kind=kind,
                description=_summarize_pages(pages),
                folder_id=folder_id,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                page_count=len(pages) if kind == "pdf" else None,
                line_count=sum(page.count("\n") + 1 for page in pages) if kind != "pdf" else None,
            )
            self.put_pages(doc_id, pages)
            document = self.get_document(doc_id)
            if document:
                self._insert_document_version(document, action=version_action, actor_user_id=actor_user_id)
            if actor_user_id and workspace_id:
                details = {"kind": kind, "name": name or path.name}
                if audit_details:
                    details.update(audit_details)
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    audit_action,
                    target_type="document",
                    target_id=doc_id,
                    details=details,
                )
        return doc_id

    def _insert_document_version(
        self,
        document: dict[str, Any],
        *,
        action: str,
        actor_user_id: str | None,
    ) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM document_versions WHERE doc_id = ?",
            (document["id"],),
        ).fetchone()
        version = int(row["version"])
        created_at = _now()
        version_id = f"docver_{uuid.uuid4().hex}"
        source_name = Path(str(document["source_path"])).name
        self.conn.execute(
            """
            INSERT INTO document_versions (
              id, doc_id, workspace_id, version, action, actor_user_id, name,
              kind, source_name, page_count, line_count, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                document["id"],
                document["workspace_id"],
                version,
                action,
                actor_user_id,
                document["name"],
                document["kind"],
                source_name,
                document["page_count"],
                document["line_count"],
                created_at,
            ),
        )
        return {
            "id": version_id,
            "doc_id": document["id"],
            "workspace_id": document["workspace_id"],
            "version": version,
            "action": action,
            "actor_user_id": actor_user_id,
            "name": document["name"],
            "kind": document["kind"],
            "source_name": source_name,
            "page_count": document["page_count"],
            "line_count": document["line_count"],
            "created_at": created_at,
        }

    def list_document_versions(
        self,
        doc_id: str,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        document = self.get_document(doc_id)
        if not document:
            return []
        if workspace_id and document["workspace_id"] != workspace_id:
            return []
        if document["workspace_id"]:
            if not actor_user_id:
                raise PermissionError("workspace access denied")
            self.require_workspace_access(document["workspace_id"], actor_user_id)
            if not self._can_read_document(document, actor_user_id):
                return []
        rows = self.conn.execute(
            """
            SELECT id, doc_id, workspace_id, version, action, actor_user_id, name,
                   kind, source_name, page_count, line_count, created_at
            FROM document_versions
            WHERE doc_id = ?
            ORDER BY version DESC
            LIMIT ?
            """,
            (doc_id, limit),
        )
        return [dict(row) for row in rows]

    def list_document_pages(
        self,
        doc_id: str,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
        max_chars: int = 4000,
    ) -> dict[str, Any]:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        document = self.get_document(doc_id)
        if not document:
            return {"doc_id": doc_id, "pages": [], "total_pages": 0}
        if workspace_id and document["workspace_id"] != workspace_id:
            return {"doc_id": doc_id, "pages": [], "total_pages": 0}
        if document["workspace_id"]:
            if not actor_user_id:
                raise PermissionError("workspace access denied")
            self.require_workspace_access(document["workspace_id"], actor_user_id)
            if not self._can_read_document(document, actor_user_id):
                return {"doc_id": doc_id, "pages": [], "total_pages": 0}
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        max_chars = max(200, min(int(max_chars), 20000))
        total_pages = int(
            self.conn.execute(
                "SELECT COUNT(*) AS count FROM document_pages WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()["count"]
        )
        rows = self.conn.execute(
            """
            SELECT page, content
            FROM document_pages
            WHERE doc_id = ?
            ORDER BY page
            LIMIT ? OFFSET ?
            """,
            (doc_id, limit, offset),
        )
        pages = []
        for row in rows:
            content = row["content"]
            truncated = len(content) > max_chars
            pages.append(
                {
                    "page": row["page"],
                    "content": content[:max_chars],
                    "truncated": truncated,
                }
            )
        return {"doc_id": doc_id, "pages": pages, "total_pages": total_pages}

    def suggest_document_questions(
        self,
        doc_id: str,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        document = self.get_document(doc_id)
        if not document:
            return {"doc_id": doc_id, "questions": []}
        if workspace_id and document["workspace_id"] != workspace_id:
            return {"doc_id": doc_id, "questions": []}
        if document["workspace_id"]:
            if not actor_user_id:
                raise PermissionError("workspace access denied")
            self.require_workspace_access(document["workspace_id"], actor_user_id)
            if not self._can_read_document(document, actor_user_id):
                return {"doc_id": doc_id, "questions": []}
        limit = max(1, min(int(limit), 8))
        rows = self.conn.execute(
            """
            SELECT content
            FROM document_pages
            WHERE doc_id = ?
            ORDER BY page
            LIMIT 3
            """,
            (doc_id,),
        )
        sample_text = " ".join(row["content"][:2000] for row in rows)
        subject = _question_subject(document["name"])
        keywords = _question_keywords(f"{document['name']} {document['description']} {sample_text}")
        questions = [
            f"What are the key takeaways from {subject}?",
            f"Which pages provide the strongest evidence in {subject}?",
        ]
        for keyword in keywords[:4]:
            questions.append(f"What does {subject} say about {keyword}?")
        if keywords:
            questions.append(f"Which page first discusses {keywords[0]}?")
        unique_questions: list[str] = []
        seen: set[str] = set()
        for question in questions:
            normalized = question.casefold()
            if normalized not in seen:
                seen.add(normalized)
                unique_questions.append(question[:240])
            if len(unique_questions) >= limit:
                break
        return {"doc_id": doc_id, "questions": unique_questions}

    def create_document_share_link(
        self,
        doc_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        expires_at: str | None = None,
        redact_content: bool = False,
        max_views: int | None = None,
        password: str | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(redact_content, bool):
            raise ValueError("redact_content must be a boolean")
        max_views = _normalize_share_max_views(max_views)
        password_salt, password_hash = _share_password_fields(password)
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        document = self.get_document(doc_id)
        if not document or document["workspace_id"] != workspace_id:
            return None
        if not document["workspace_id"]:
            raise ValueError("document share links require a workspace document")
        self._require_document_write(document, actor_user_id)
        expires_at = _normalize_expires_at(expires_at)
        token = f"pis_{secrets.token_urlsafe(32)}"
        share_link_id = f"dsl_{uuid.uuid4().hex}"
        created_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO document_share_links (
                  id, workspace_id, doc_id, created_by, token_hash,
                  password_salt, password_hash, redact_content, max_views,
                  created_at, expires_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    share_link_id,
                    workspace_id,
                    document["id"],
                    actor_user_id.strip(),
                    _hash_token(token),
                    password_salt,
                    password_hash,
                    1 if redact_content else 0,
                    max_views,
                    created_at,
                    expires_at,
                ),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "document.share_link_create",
                target_type="document",
                target_id=document["id"],
                details={
                    "share_link_id": share_link_id,
                    "expires_at": expires_at,
                    "redact_content": redact_content,
                    "max_views": max_views,
                    "password_protected": password_hash is not None,
                },
            )
        link = self._document_share_link(share_link_id)
        assert link is not None
        link["token"] = token
        return link

    def list_document_share_links(
        self,
        doc_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
    ) -> list[dict[str, Any]]:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        document = self.get_document(doc_id)
        if not document or document["workspace_id"] != workspace_id:
            return []
        self._require_document_write(document, actor_user_id)
        rows = self.conn.execute(
            """
            SELECT id, workspace_id, doc_id, created_by, redact_content, max_views,
                   password_hash IS NOT NULL AS password_protected, view_count, last_viewed_at,
                   created_at, expires_at, revoked_at
            FROM document_share_links
            WHERE doc_id = ?
            ORDER BY created_at DESC, id
            """,
            (document["id"],),
        )
        return [_decorate_document_share_link(dict(row)) for row in rows]

    def revoke_document_share_link(
        self,
        share_link_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
    ) -> bool:
        share_link_id = share_link_id.strip()
        if not share_link_id:
            raise ValueError("Share link id is required.")
        link = self._one("SELECT * FROM document_share_links WHERE id = ?", (share_link_id,))
        if not link or link["workspace_id"] != workspace_id:
            return False
        document = self.get_document(link["doc_id"])
        if not document or document["workspace_id"] != workspace_id:
            return False
        self._require_document_write(document, actor_user_id)
        if link["revoked_at"] is not None:
            return False
        revoked_at = _now()
        with self._atomic():
            self.conn.execute(
                "UPDATE document_share_links SET revoked_at = ? WHERE id = ?",
                (revoked_at, share_link_id),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "document.share_link_revoke",
                target_type="document",
                target_id=document["id"],
                details={"share_link_id": share_link_id},
            )
        return True

    def record_document_share_link_view(
        self,
        token: str,
        *,
        password: str | None = None,
        response_format: str,
        limit: int,
        offset: int,
        max_chars: int,
    ) -> bool:
        token = token.strip()
        if not token:
            raise ValueError("Share token is required.")
        token_hash = _hash_token(token)
        row = self._one(
            """
            SELECT id, workspace_id, doc_id, token_hash, password_salt, password_hash,
                   redact_content, expires_at, revoked_at
            FROM document_share_links
            WHERE token_hash = ?
            """,
            (token_hash,),
        )
        if not row or not hmac.compare_digest(row["token_hash"], token_hash):
            return False
        if not _share_password_matches(password, row["password_salt"], row["password_hash"]):
            return False
        if row["revoked_at"] is not None or _is_expired(row["expires_at"]):
            return False
        viewed_at = _now()
        with self._atomic():
            cursor = self.conn.execute(
                """
                UPDATE document_share_links
                SET view_count = view_count + 1, last_viewed_at = ?
                WHERE id = ?
                  AND revoked_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                  AND (max_views IS NULL OR view_count < max_views)
                """,
                (viewed_at, row["id"], viewed_at),
            )
            if cursor.rowcount != 1:
                return False
            self._insert_audit_event(
                row["workspace_id"],
                "public",
                "document.share_link_view",
                target_type="document",
                target_id=row["doc_id"],
                details={
                    "share_link_id": row["id"],
                    "response_format": response_format,
                    "redact_content": bool(row["redact_content"]),
                    "limit": limit,
                    "offset": offset,
                    "max_chars": max_chars,
                },
            )
        return True

    def resolve_document_share_link(
        self,
        token: str,
        *,
        password: str | None = None,
        limit: int = 20,
        offset: int = 0,
        max_chars: int = 4000,
    ) -> dict[str, Any] | None:
        token = token.strip()
        if not token:
            raise ValueError("Share token is required.")
        token_hash = _hash_token(token)
        row = self._one(
            """
            SELECT l.id AS share_link_id, l.workspace_id, l.doc_id, l.created_by,
                   l.token_hash, l.password_salt, l.password_hash,
                   l.redact_content, l.max_views, l.view_count,
                   l.created_at, l.expires_at, l.revoked_at,
                   d.name, d.description, d.kind, d.access_mode, d.page_count, d.line_count
            FROM document_share_links l
            JOIN documents d ON d.id = l.doc_id
            WHERE l.token_hash = ?
            """,
            (token_hash,),
        )
        if not row or not hmac.compare_digest(row["token_hash"], token_hash):
            return None
        if not _share_password_matches(password, row["password_salt"], row["password_hash"]):
            return None
        if row["revoked_at"] is not None or _is_expired(row["expires_at"]):
            return None
        if _share_link_view_limit_reached(row["view_count"], row["max_views"]):
            return None
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        max_chars = max(200, min(int(max_chars), 20000))
        redact_content = bool(row["redact_content"])
        total_pages = int(
            self.conn.execute(
                "SELECT COUNT(*) AS count FROM document_pages WHERE doc_id = ?",
                (row["doc_id"],),
            ).fetchone()["count"]
        )
        pages = []
        for page in self.conn.execute(
            """
            SELECT page, content
            FROM document_pages
            WHERE doc_id = ?
            ORDER BY page
            LIMIT ? OFFSET ?
            """,
            (row["doc_id"], limit, offset),
        ):
            content = page["content"]
            if redact_content:
                content = _redact_public_share_text(content)
            pages.append(
                {
                    "page": page["page"],
                    "content": content[:max_chars],
                    "truncated": len(content) > max_chars,
                }
            )
        share_link = _decorate_document_share_link(
            {
                "id": row["share_link_id"],
                "workspace_id": row["workspace_id"],
                "doc_id": row["doc_id"],
                "created_by": row["created_by"],
                "redact_content": row["redact_content"],
                "max_views": row["max_views"],
                "password_protected": row["password_hash"] is not None,
                "view_count": row["view_count"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "revoked_at": row["revoked_at"],
            }
        )
        share_link = _strip_public_share_link_management_fields(share_link)
        document = {
            "id": row["doc_id"],
            "workspace_id": row["workspace_id"],
            "name": _redact_public_share_text(row["name"]) if redact_content else row["name"],
            "description": _redact_public_share_text(row["description"]) if redact_content else row["description"],
            "kind": row["kind"],
            "access_mode": row["access_mode"],
            "page_count": row["page_count"],
            "line_count": row["line_count"],
        }
        if redact_content:
            share_link = _minimize_redacted_public_share_link(share_link, "doc_id")
            document = _minimize_redacted_public_entity(document, ("id", "workspace_id", "access_mode"))
        return {
            "share_link": share_link,
            "document": document,
            "pages": pages,
            "total_pages": total_pages,
        }

    def get_managed_upload_document_file(
        self,
        doc_id: str,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        document = self.get_document(doc_id)
        if not document:
            return None
        if workspace_id and document["workspace_id"] != workspace_id:
            return None
        if not document["workspace_id"]:
            raise ValueError("document download is available only for managed uploads")
        if not actor_user_id:
            raise PermissionError("workspace access denied")
        self.require_workspace_access(document["workspace_id"], actor_user_id)
        if not self._can_read_document(document, actor_user_id):
            return None
        uploads_root = (self.root / "uploads").resolve()
        upload_dir = (uploads_root / _safe_storage_segment(document["workspace_id"])).resolve()
        if not _path_is_relative_to(upload_dir, uploads_root):
            raise ValueError("workspace upload path is invalid")
        source_path = Path(str(document["source_path"])).expanduser().resolve()
        if not _path_is_relative_to(source_path, upload_dir):
            raise ValueError("document download is available only for managed uploads")
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        return {"document": document, "path": source_path}

    def rename_document(
        self,
        doc_id: str,
        name: str,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        if not isinstance(name, str):
            raise ValueError("Document name is required.")
        name = name.strip()
        if not name:
            raise ValueError("Document name is required.")
        document = self.get_document(doc_id)
        if not document:
            return None
        if workspace_id and document["workspace_id"] != workspace_id:
            return None
        self._require_document_write(document, actor_user_id)
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                UPDATE documents
                SET name = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, now, document["id"]),
            )
            if actor_user_id and document["workspace_id"]:
                self._insert_audit_event(
                    document["workspace_id"],
                    actor_user_id,
                    "document.rename",
                    target_type="document",
                    target_id=document["id"],
                    details={
                        "name_length": len(name),
                        "previous_name_length": len(document["name"]),
                        "kind": document["kind"],
                    },
                )
        return self.get_document(document["id"])

    def move_document(
        self,
        doc_id: str,
        folder_id: str | None = None,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        if folder_id is not None and not isinstance(folder_id, str):
            raise ValueError("folder_id must be a string")
        target_folder_id = folder_id.strip() if folder_id else None
        document = self.get_document(doc_id)
        if not document:
            return None
        if workspace_id and document["workspace_id"] != workspace_id:
            return None
        self._require_document_write(document, actor_user_id)
        if target_folder_id:
            folder = self._one("SELECT id, workspace_id FROM folders WHERE id = ?", (target_folder_id,))
            if not folder:
                raise ValueError(f"Folder not found: {target_folder_id}")
            if folder["workspace_id"] != document["workspace_id"]:
                raise PermissionError("folder access denied")
        if (document["folder_id"] or None) == target_folder_id:
            return document
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                UPDATE documents
                SET folder_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (target_folder_id, now, document["id"]),
            )
            if actor_user_id and document["workspace_id"]:
                self._insert_audit_event(
                    document["workspace_id"],
                    actor_user_id,
                    "document.move",
                    target_type="document",
                    target_id=document["id"],
                    details={
                        "previous_folder_id": document["folder_id"],
                        "folder_id": target_folder_id,
                    },
                )
        return self.get_document(document["id"])

    def reindex_document_file(
        self,
        doc_id: str,
        file_path: str | Path,
        *,
        name: str | None = None,
        folder_id: str | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> dict[str, Any] | None:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        document = self.get_document(doc_id)
        if not document:
            return None
        if workspace_id and document["workspace_id"] != workspace_id:
            return None
        self._require_document_write(document, actor_user_id)
        replacement_name = document["name"] if name is None else name.strip()
        if not replacement_name:
            raise ValueError("Document name is required.")
        target_folder_id = document["folder_id"] if folder_id is None else folder_id
        updated_id = self.ingest_file(
            file_path,
            folder_id=target_folder_id,
            doc_id=doc_id,
            name=replacement_name,
            workspace_id=document["workspace_id"],
            actor_user_id=actor_user_id,
            audit_action="document.reindex",
            audit_details={"previous_kind": document["kind"]},
        )
        return self.get_document(updated_id)

    def put_pages(self, doc_id: str, pages: list[str]) -> None:
        document = self.get_document(doc_id)
        if not document:
            raise ValueError(f"Document not found: {doc_id}")
        current_pages = int(
            self.conn.execute(
                "SELECT COUNT(*) AS count FROM document_pages WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()["count"]
        )
        pages_delta = len(pages) - current_pages
        if pages_delta > 0:
            self._enforce_workspace_quota(document.get("workspace_id"), pages_delta=pages_delta)
        self.conn.execute("DELETE FROM document_pages WHERE doc_id = ?", (doc_id,))
        self.conn.executemany(
            "INSERT INTO document_pages (doc_id, page, content) VALUES (?, ?, ?)",
            [(doc_id, i + 1, content) for i, content in enumerate(pages)],
        )
        self._commit()

    def _purge_document_index(self, doc_id: str) -> None:
        self.conn.execute("DELETE FROM citations WHERE doc_id = ?", (doc_id,))
        self.conn.execute("DELETE FROM evidence WHERE doc_id = ?", (doc_id,))
        self.conn.execute("DELETE FROM virtual_node_docs WHERE doc_id = ?", (doc_id,))
        self.conn.execute("DELETE FROM virtual_nodes WHERE doc_id = ?", (doc_id,))
        self.conn.execute("DELETE FROM document_pages WHERE doc_id = ?", (doc_id,))

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM documents WHERE id = ?", (doc_id,))
        return dict(row) if row else None

    def _query_source_set_row(self, workspace_id: str, source_set_id: str) -> dict[str, Any] | None:
        row = self._one(
            """
            SELECT id, workspace_id, name, description, shared, created_by, created_at, updated_at
            FROM query_source_sets
            WHERE workspace_id = ? AND id = ?
            """,
            (workspace_id, source_set_id.strip()),
        )
        if not row:
            return None
        source_set = dict(row)
        source_set["shared"] = bool(source_set.get("shared"))
        return source_set

    def _can_use_query_source_set(self, workspace_id: str, actor_user_id: str, source_set: dict[str, Any]) -> bool:
        role = self.workspace_role(workspace_id, actor_user_id)
        return role in WORKSPACE_ADMIN_ROLES or bool(source_set.get("shared"))

    def _require_query_source_set_access(
        self,
        workspace_id: str,
        actor_user_id: str,
        source_set: dict[str, Any],
    ) -> None:
        self.require_workspace_access(workspace_id, actor_user_id)
        if not self._can_use_query_source_set(workspace_id, actor_user_id, source_set):
            raise PermissionError("query source set access denied")

    def _readable_documents_by_id(
        self,
        workspace_id: str,
        doc_ids: list[str],
        actor_user_id: str,
    ) -> dict[str, dict[str, Any]]:
        if not doc_ids:
            return {}
        read_condition, read_args = self._document_read_condition("d", actor_user_id)
        rows = self.conn.execute(
            f"""
            SELECT d.id, d.workspace_id, d.name, d.kind, d.access_mode
            FROM documents d
            WHERE d.workspace_id = ?
              AND d.id IN ({','.join('?' for _ in doc_ids)})
              AND {read_condition}
            """,
            (workspace_id, *doc_ids, *read_args),
        )
        return {row["id"]: dict(row) for row in rows}

    def _query_source_set_documents(
        self,
        workspace_id: str,
        source_set_id: str,
        actor_user_id: str,
    ) -> list[dict[str, Any]]:
        read_condition, read_args = self._document_read_condition("d", actor_user_id)
        rows = self.conn.execute(
            f"""
            SELECT d.id, d.workspace_id, d.name, d.kind, d.access_mode, qsd.position
            FROM query_source_set_documents qsd
            JOIN documents d ON d.id = qsd.doc_id
            WHERE qsd.workspace_id = ?
              AND qsd.source_set_id = ?
              AND d.workspace_id = ?
              AND {read_condition}
            ORDER BY qsd.position, d.name, d.id
            """,
            (workspace_id, source_set_id, workspace_id, *read_args),
        )
        return [dict(row) for row in rows]

    def get_query_source_set(
        self,
        workspace_id: str,
        actor_user_id: str,
        source_set_id: str,
    ) -> dict[str, Any] | None:
        self.require_workspace_access(workspace_id, actor_user_id)
        source_set = self._query_source_set_row(workspace_id, source_set_id)
        if not source_set:
            return None
        self._require_query_source_set_access(workspace_id, actor_user_id, source_set)
        documents = self._query_source_set_documents(workspace_id, source_set["id"], actor_user_id)
        return {
            **source_set,
            "doc_ids": [document["id"] for document in documents],
            "documents": documents,
            "document_count": len(documents),
        }

    def list_query_source_sets(self, workspace_id: str, actor_user_id: str) -> list[dict[str, Any]]:
        self.require_workspace_access(workspace_id, actor_user_id)
        role = self.workspace_role(workspace_id, actor_user_id)
        shared_filter = "" if role in WORKSPACE_ADMIN_ROLES else "AND shared = 1"
        rows = self.conn.execute(
            f"""
            SELECT id, workspace_id, name, description, shared, created_by, created_at, updated_at
            FROM query_source_sets
            WHERE workspace_id = ?
              {shared_filter}
            ORDER BY updated_at DESC, name, id
            """,
            (workspace_id,),
        )
        source_sets = []
        for row in rows:
            source_set = dict(row)
            source_set["shared"] = bool(source_set.get("shared"))
            documents = self._query_source_set_documents(workspace_id, source_set["id"], actor_user_id)
            source_sets.append(
                {
                    **source_set,
                    "doc_ids": [document["id"] for document in documents],
                    "documents": documents,
                    "document_count": len(documents),
                }
            )
        return source_sets

    def create_query_source_set(
        self,
        workspace_id: str,
        actor_user_id: str,
        name: str,
        doc_ids: list[str] | None,
        *,
        description: str | None = None,
        shared: bool = False,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        if not isinstance(shared, bool):
            raise ValueError("shared must be a boolean")
        normalized_name = _normalize_source_set_name(name)
        normalized_description = _normalize_source_set_description(description)
        normalized_doc_ids = _normalize_source_set_doc_ids(doc_ids)
        if self._one(
            "SELECT id FROM query_source_sets WHERE workspace_id = ? AND name = ?",
            (workspace_id, normalized_name),
        ):
            raise ValueError("Source set name already exists.")
        readable_documents = self._readable_documents_by_id(workspace_id, normalized_doc_ids, actor_user_id)
        if len(readable_documents) != len(normalized_doc_ids):
            raise ValueError("Source set documents must belong to the workspace and be readable.")
        source_set_id = f"qss_{uuid.uuid4().hex}"
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO query_source_sets
                  (id, workspace_id, name, description, shared, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_set_id,
                    workspace_id,
                    normalized_name,
                    normalized_description,
                    int(shared),
                    actor_user_id,
                    now,
                    now,
                ),
            )
            for position, doc_id in enumerate(normalized_doc_ids):
                self.conn.execute(
                    """
                    INSERT INTO query_source_set_documents (source_set_id, workspace_id, doc_id, position)
                    VALUES (?, ?, ?, ?)
                    """,
                    (source_set_id, workspace_id, doc_id, position),
                )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "query_source_set.create",
                target_type="query_source_set",
                target_id=source_set_id,
                details={"name": normalized_name, "document_count": len(normalized_doc_ids), "shared": shared},
            )
        created = self.get_query_source_set(workspace_id, actor_user_id, source_set_id)
        if created is None:
            raise RuntimeError("created source set could not be loaded")
        return created

    def update_query_source_set(
        self,
        workspace_id: str,
        actor_user_id: str,
        source_set_id: str,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        doc_ids: list[str] | None | object = _UNSET,
        shared: bool | object = _UNSET,
    ) -> dict[str, Any]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        source_set = self._query_source_set_row(workspace_id, source_set_id)
        if not source_set:
            raise ValueError("Query source set not found.")
        if name is _UNSET and description is _UNSET and doc_ids is _UNSET and shared is _UNSET:
            raise ValueError("At least one source set update is required.")
        if name is _UNSET:
            normalized_name = source_set["name"]
        elif not isinstance(name, str):
            raise ValueError("Source set name must be a string.")
        else:
            normalized_name = _normalize_source_set_name(name)
        if description is _UNSET:
            normalized_description = source_set["description"]
        elif description is not None and not isinstance(description, str):
            raise ValueError("Source set description must be a string.")
        else:
            normalized_description = _normalize_source_set_description(description)
        if shared is _UNSET:
            normalized_shared = bool(source_set["shared"])
        elif not isinstance(shared, bool):
            raise ValueError("shared must be a boolean")
        else:
            normalized_shared = shared
        normalized_doc_ids: list[str] | None = None
        if doc_ids is not _UNSET:
            if doc_ids is not None and not isinstance(doc_ids, list):
                raise ValueError("Document ids must be a list.")
            normalized_doc_ids = _normalize_source_set_doc_ids(doc_ids)
            readable_documents = self._readable_documents_by_id(workspace_id, normalized_doc_ids, actor_user_id)
            if len(readable_documents) != len(normalized_doc_ids):
                raise ValueError("Source set documents must belong to the workspace and be readable.")
        duplicate = self._one(
            "SELECT id FROM query_source_sets WHERE workspace_id = ? AND name = ? AND id <> ?",
            (workspace_id, normalized_name, source_set["id"]),
        )
        if duplicate:
            raise ValueError("Source set name already exists.")
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                UPDATE query_source_sets
                SET name = ?, description = ?, shared = ?, updated_at = ?
                WHERE id = ? AND workspace_id = ?
                """,
                (normalized_name, normalized_description, int(normalized_shared), now, source_set["id"], workspace_id),
            )
            if normalized_doc_ids is not None:
                self.conn.execute(
                    "DELETE FROM query_source_set_documents WHERE source_set_id = ? AND workspace_id = ?",
                    (source_set["id"], workspace_id),
                )
                for position, doc_id in enumerate(normalized_doc_ids):
                    self.conn.execute(
                        """
                        INSERT INTO query_source_set_documents (source_set_id, workspace_id, doc_id, position)
                        VALUES (?, ?, ?, ?)
                        """,
                        (source_set["id"], workspace_id, doc_id, position),
                    )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "query_source_set.update",
                target_type="query_source_set",
                target_id=source_set["id"],
                details={
                    "name": normalized_name,
                    "previous_name": source_set["name"],
                    "document_count": len(normalized_doc_ids) if normalized_doc_ids is not None else None,
                    "shared": normalized_shared,
                    "previous_shared": bool(source_set["shared"]),
                },
            )
        updated = self.get_query_source_set(workspace_id, actor_user_id, source_set["id"])
        if updated is None:
            raise RuntimeError("updated source set could not be loaded")
        return updated

    def delete_query_source_set(self, workspace_id: str, actor_user_id: str, source_set_id: str) -> bool:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        source_set = self._query_source_set_row(workspace_id, source_set_id)
        if not source_set:
            return False
        with self._atomic():
            self.conn.execute("DELETE FROM query_source_sets WHERE id = ? AND workspace_id = ?", (source_set["id"], workspace_id))
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "query_source_set.delete",
                target_type="query_source_set",
                target_id=source_set["id"],
                details={"name": source_set["name"]},
            )
        return True

    def _query_source_set_share_link(self, share_link_id: str) -> dict[str, Any] | None:
        row = self._one(
            """
            SELECT id, workspace_id, source_set_id, created_by, redact_content, max_views,
                   password_hash IS NOT NULL AS password_protected, view_count, last_viewed_at,
                   created_at, expires_at, revoked_at
            FROM query_source_set_share_links
            WHERE id = ?
            """,
            (share_link_id,),
        )
        return _decorate_source_set_share_link(dict(row)) if row else None

    def create_query_source_set_share_link(
        self,
        workspace_id: str,
        actor_user_id: str,
        source_set_id: str,
        *,
        expires_at: str | None = None,
        redact_content: bool = False,
        max_views: int | None = None,
        password: str | None = None,
    ) -> dict[str, Any] | None:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        if not isinstance(redact_content, bool):
            raise ValueError("redact_content must be a boolean")
        source_set = self._query_source_set_row(workspace_id, source_set_id)
        if not source_set:
            return None
        max_views = _normalize_share_max_views(max_views)
        password_salt, password_hash = _share_password_fields(password)
        expires_at = _normalize_expires_at(expires_at)
        token = f"pss_{secrets.token_urlsafe(32)}"
        share_link_id = f"qssl_{uuid.uuid4().hex}"
        created_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO query_source_set_share_links (
                  id, workspace_id, source_set_id, created_by, token_hash,
                  password_salt, password_hash, redact_content, max_views,
                  created_at, expires_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    share_link_id,
                    workspace_id,
                    source_set["id"],
                    actor_user_id.strip(),
                    _hash_token(token),
                    password_salt,
                    password_hash,
                    1 if redact_content else 0,
                    max_views,
                    created_at,
                    expires_at,
                ),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "query_source_set.share_link_create",
                target_type="query_source_set",
                target_id=source_set["id"],
                details={
                    "share_link_id": share_link_id,
                    "expires_at": expires_at,
                    "redact_content": redact_content,
                    "max_views": max_views,
                    "password_protected": password_hash is not None,
                },
            )
        link = self._query_source_set_share_link(share_link_id)
        assert link is not None
        link["token"] = token
        return link

    def list_query_source_set_share_links(
        self,
        workspace_id: str,
        actor_user_id: str,
        source_set_id: str,
    ) -> list[dict[str, Any]]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        source_set = self._query_source_set_row(workspace_id, source_set_id)
        if not source_set:
            return []
        rows = self.conn.execute(
            """
            SELECT id, workspace_id, source_set_id, created_by, redact_content, max_views,
                   password_hash IS NOT NULL AS password_protected, view_count, last_viewed_at,
                   created_at, expires_at, revoked_at
            FROM query_source_set_share_links
            WHERE source_set_id = ?
            ORDER BY created_at DESC, id
            """,
            (source_set["id"],),
        )
        return [_decorate_source_set_share_link(dict(row)) for row in rows]

    def revoke_query_source_set_share_link(
        self,
        workspace_id: str,
        actor_user_id: str,
        share_link_id: str,
    ) -> bool:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        share_link_id = share_link_id.strip()
        if not share_link_id:
            raise ValueError("Share link id is required.")
        link = self._one("SELECT * FROM query_source_set_share_links WHERE id = ?", (share_link_id,))
        if not link or link["workspace_id"] != workspace_id:
            return False
        source_set = self._query_source_set_row(workspace_id, link["source_set_id"])
        if not source_set or link["revoked_at"] is not None:
            return False
        revoked_at = _now()
        with self._atomic():
            self.conn.execute(
                "UPDATE query_source_set_share_links SET revoked_at = ? WHERE id = ?",
                (revoked_at, share_link_id),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "query_source_set.share_link_revoke",
                target_type="query_source_set",
                target_id=source_set["id"],
                details={"share_link_id": share_link_id},
            )
        return True

    def _public_query_source_set_documents(self, source_set_id: str, *, limit: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT d.id, d.workspace_id, d.name, d.description, d.kind, d.access_mode,
                   d.page_count, d.line_count, qsd.position
            FROM query_source_set_documents qsd
            JOIN documents d ON d.id = qsd.doc_id
            WHERE qsd.source_set_id = ?
            ORDER BY qsd.position, d.name, d.id
            LIMIT ?
            """,
            (source_set_id, limit),
        )
        return [dict(row) for row in rows]

    def resolve_query_source_set_share_link(
        self,
        token: str,
        *,
        password: str | None = None,
        document_limit: int = 100,
    ) -> dict[str, Any] | None:
        token = token.strip()
        if not token:
            raise ValueError("Share token is required.")
        token_hash = _hash_token(token)
        row = self._one(
            """
            SELECT l.id AS share_link_id, l.workspace_id, l.source_set_id, l.created_by,
                   l.token_hash, l.password_salt, l.password_hash,
                   l.redact_content, l.max_views, l.view_count,
                   l.created_at, l.expires_at, l.revoked_at,
                   q.name, q.description, q.shared, q.created_at AS source_set_created_at,
                   q.updated_at
            FROM query_source_set_share_links l
            JOIN query_source_sets q ON q.id = l.source_set_id
            WHERE l.token_hash = ?
            """,
            (token_hash,),
        )
        if not row or not hmac.compare_digest(row["token_hash"], token_hash):
            return None
        if not _share_password_matches(password, row["password_salt"], row["password_hash"]):
            return None
        if row["revoked_at"] is not None or _is_expired(row["expires_at"]):
            return None
        if _share_link_view_limit_reached(row["view_count"], row["max_views"]):
            return None
        document_limit = max(1, min(int(document_limit), 500))
        redact_content = bool(row["redact_content"])
        documents = self._public_query_source_set_documents(row["source_set_id"], limit=document_limit)
        total_documents_row = self._one(
            "SELECT COUNT(*) AS count FROM query_source_set_documents WHERE source_set_id = ?",
            (row["source_set_id"],),
        )
        public_documents = []
        for document in documents:
            public_documents.append(
                {
                    "name": _redact_public_share_text(document["name"]) if redact_content else document["name"],
                    "description": _redact_public_share_text(document["description"])
                    if redact_content
                    else document["description"],
                    "kind": document["kind"],
                    "page_count": document["page_count"],
                    "line_count": document["line_count"],
                    "position": document["position"],
                }
            )
        share_link = _decorate_source_set_share_link(
            {
                "id": row["share_link_id"],
                "workspace_id": row["workspace_id"],
                "source_set_id": row["source_set_id"],
                "created_by": row["created_by"],
                "redact_content": row["redact_content"],
                "max_views": row["max_views"],
                "password_protected": row["password_hash"] is not None,
                "view_count": row["view_count"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "revoked_at": row["revoked_at"],
            }
        )
        share_link = _strip_public_share_link_management_fields(
            _minimize_redacted_public_share_link(share_link, "source_set_id")
        )
        source_set = {
            "name": _redact_public_share_text(row["name"]) if redact_content else row["name"],
            "description": _redact_public_share_text(row["description"]) if redact_content else row["description"],
            "created_at": row["source_set_created_at"],
            "updated_at": row["updated_at"],
            "document_count": int(total_documents_row["count"]) if total_documents_row else len(documents),
            "documents_returned": len(public_documents),
        }
        return {"share_link": share_link, "source_set": source_set, "documents": public_documents}

    def record_query_source_set_share_link_view(
        self,
        token: str,
        *,
        password: str | None = None,
        response_format: str,
        document_limit: int,
    ) -> bool:
        token = token.strip()
        if not token:
            raise ValueError("Share token is required.")
        token_hash = _hash_token(token)
        row = self._one(
            """
            SELECT id, workspace_id, source_set_id, token_hash, password_salt, password_hash,
                   redact_content, expires_at, revoked_at
            FROM query_source_set_share_links
            WHERE token_hash = ?
            """,
            (token_hash,),
        )
        if not row or not hmac.compare_digest(row["token_hash"], token_hash):
            return False
        if not _share_password_matches(password, row["password_salt"], row["password_hash"]):
            return False
        if row["revoked_at"] is not None or _is_expired(row["expires_at"]):
            return False
        viewed_at = _now()
        with self._atomic():
            cursor = self.conn.execute(
                """
                UPDATE query_source_set_share_links
                SET view_count = view_count + 1, last_viewed_at = ?
                WHERE id = ?
                  AND revoked_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                  AND (max_views IS NULL OR view_count < max_views)
                """,
                (viewed_at, row["id"], viewed_at),
            )
            if cursor.rowcount != 1:
                return False
            self._insert_audit_event(
                row["workspace_id"],
                "public",
                "query_source_set.share_link_view",
                target_type="query_source_set",
                target_id=row["source_set_id"],
                details={
                    "share_link_id": row["id"],
                    "response_format": response_format,
                    "redact_content": bool(row["redact_content"]),
                    "document_limit": document_limit,
                },
            )
        return True

    def resolve_query_source_set_doc_ids(
        self,
        workspace_id: str,
        actor_user_id: str,
        source_set_id: str,
    ) -> list[str]:
        self.require_workspace_access(workspace_id, actor_user_id)
        source_set = self._query_source_set_row(workspace_id, source_set_id)
        if source_set is None:
            raise ValueError("Query source set not found.")
        self._require_query_source_set_access(workspace_id, actor_user_id, source_set)
        documents = self._query_source_set_documents(workspace_id, source_set["id"], actor_user_id)
        return [document["id"] for document in documents]

    def resolve_query_folder_scope(
        self,
        workspace_id: str,
        actor_user_id: str,
        folder_id: str,
    ) -> dict[str, Any]:
        self.require_workspace_access(workspace_id, actor_user_id)
        if not isinstance(folder_id, str):
            raise ValueError("folder_id must be a string")
        folder_id = folder_id.strip()
        if not folder_id:
            raise ValueError("folder_id is required")
        folder = self._one(
            "SELECT id, workspace_id, path FROM folders WHERE id = ?",
            (folder_id,),
        )
        if folder is None or folder["workspace_id"] != workspace_id:
            raise ValueError(f"Folder not found: {folder_id}")
        read_condition, read_args = self._document_read_condition("d", actor_user_id)
        descendant_pattern = f"{_escape_like(folder['path'])}/%"
        rows = self.conn.execute(
            f"""
            SELECT d.id
            FROM documents d
            JOIN folders f ON f.id = d.folder_id
            WHERE d.workspace_id = ?
              AND (f.path = ? OR f.path LIKE ? ESCAPE '\\')
              AND {read_condition}
            ORDER BY f.path, d.name, d.id
            """,
            (workspace_id, folder["path"], descendant_pattern, *read_args),
        )
        doc_ids = [row["id"] for row in rows]
        return {
            "folder_id": folder["id"],
            "folder_path": folder["path"],
            "doc_ids": doc_ids,
            "folder_document_count": len(doc_ids),
        }

    def list_documents(
        self,
        folder_id: str | None = None,
        workspace_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        actor_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        read_condition, read_args = self._document_read_condition("d", actor_user_id)
        if folder_id and workspace_id:
            rows = self.conn.execute(
                f"""
                SELECT d.* FROM documents d
                WHERE d.folder_id = ? AND d.workspace_id = ? AND {read_condition}
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (folder_id, workspace_id, *read_args, limit, offset),
            )
        elif folder_id:
            rows = self.conn.execute(
                f"""
                SELECT d.* FROM documents d
                WHERE d.folder_id = ? AND {read_condition}
                ORDER BY d.created_at DESC LIMIT ? OFFSET ?
                """,
                (folder_id, *read_args, limit, offset),
            )
        elif workspace_id:
            rows = self.conn.execute(
                f"""
                SELECT d.* FROM documents d
                WHERE d.workspace_id = ? AND {read_condition}
                ORDER BY d.created_at DESC LIMIT ? OFFSET ?
                """,
                (workspace_id, *read_args, limit, offset),
            )
        else:
            rows = self.conn.execute(
                f"""
                SELECT d.* FROM documents d
                WHERE {read_condition}
                ORDER BY d.created_at DESC LIMIT ? OFFSET ?
                """,
                (*read_args, limit, offset),
            )
        return [dict(row) for row in rows]

    def list_document_access(
        self,
        doc_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
    ) -> dict[str, Any] | None:
        document = self.get_document(doc_id.strip())
        if not document or document["workspace_id"] != workspace_id:
            return None
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        rows = self.conn.execute(
            """
            SELECT doc_id, workspace_id, user_id, role, granted_by, created_at
            FROM document_access_grants
            WHERE doc_id = ?
            ORDER BY user_id
            """,
            (document["id"],),
        )
        group_rows = self.conn.execute(
            """
            SELECT dg.doc_id, dg.workspace_id, dg.group_id, g.name AS group_name,
                   dg.role, dg.granted_by, dg.created_at
            FROM document_group_access_grants dg
            JOIN workspace_groups g ON g.id = dg.group_id
            WHERE dg.doc_id = ?
            ORDER BY g.name, dg.group_id
            """,
            (document["id"],),
        )
        return {
            "doc_id": document["id"],
            "workspace_id": workspace_id,
            "access_mode": document.get("access_mode", "workspace"),
            "grants": [dict(row) for row in rows],
            "group_grants": [dict(row) for row in group_rows],
        }

    def set_document_access_mode(
        self,
        doc_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        access_mode: str,
    ) -> dict[str, Any] | None:
        document = self.get_document(doc_id.strip())
        if not document or document["workspace_id"] != workspace_id:
            return None
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        access_mode = _normalize_document_access_mode(access_mode)
        with self._atomic():
            self.conn.execute(
                "UPDATE documents SET access_mode = ?, updated_at = ? WHERE id = ?",
                (access_mode, _now(), document["id"]),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "document.access_mode",
                target_type="document",
                target_id=document["id"],
                details={"access_mode": access_mode, "previous_access_mode": document.get("access_mode", "workspace")},
            )
        return self.list_document_access(document["id"], workspace_id=workspace_id, actor_user_id=actor_user_id)

    def grant_document_access(
        self,
        doc_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        user_id: str,
        role: str = "read",
    ) -> dict[str, Any] | None:
        document = self.get_document(doc_id.strip())
        if not document or document["workspace_id"] != workspace_id:
            return None
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        user_id = user_id.strip()
        if not user_id:
            raise ValueError("User id is required.")
        self.require_workspace_access(workspace_id, user_id)
        role = _normalize_document_access_role(role)
        if role == "write" and self.workspace_role(workspace_id, user_id) not in WORKSPACE_WRITE_ROLES:
            raise PermissionError("document write grant requires workspace write role")
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO document_access_grants (doc_id, workspace_id, user_id, role, granted_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id, user_id) DO UPDATE SET
                  role = excluded.role,
                  granted_by = excluded.granted_by,
                  created_at = excluded.created_at
                """,
                (document["id"], workspace_id, user_id, role, actor_user_id, now),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "document.access_grant",
                target_type="document",
                target_id=document["id"],
                details={"user_id": user_id, "role": role},
            )
        return self.list_document_access(document["id"], workspace_id=workspace_id, actor_user_id=actor_user_id)

    def grant_document_group_access(
        self,
        doc_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        group_id: str,
        role: str = "read",
    ) -> dict[str, Any] | None:
        document = self.get_document(doc_id.strip())
        if not document or document["workspace_id"] != workspace_id:
            return None
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._require_workspace_group(workspace_id, group_id)
        role = _normalize_document_access_role(role)
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO document_group_access_grants (doc_id, workspace_id, group_id, role, granted_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id, group_id) DO UPDATE SET
                  role = excluded.role,
                  granted_by = excluded.granted_by,
                  created_at = excluded.created_at
                """,
                (document["id"], workspace_id, group["id"], role, actor_user_id, now),
            )
            self._insert_audit_event(
                workspace_id,
                actor_user_id,
                "document.group_access_grant",
                target_type="document",
                target_id=document["id"],
                details={"group_id": group["id"], "group_name": group["name"], "role": role},
            )
        return self.list_document_access(document["id"], workspace_id=workspace_id, actor_user_id=actor_user_id)

    def revoke_document_access(
        self,
        doc_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        user_id: str,
    ) -> bool:
        document = self.get_document(doc_id.strip())
        if not document or document["workspace_id"] != workspace_id:
            return False
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        user_id = user_id.strip()
        if not user_id:
            raise ValueError("User id is required.")
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM document_access_grants WHERE doc_id = ? AND user_id = ?",
                (document["id"], user_id),
            )
            revoked = cursor.rowcount > 0
            if revoked:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "document.access_revoke",
                    target_type="document",
                    target_id=document["id"],
                    details={"user_id": user_id, "role": "read"},
                )
        return revoked

    def revoke_document_group_access(
        self,
        doc_id: str,
        *,
        workspace_id: str,
        actor_user_id: str,
        group_id: str,
    ) -> bool:
        document = self.get_document(doc_id.strip())
        if not document or document["workspace_id"] != workspace_id:
            return False
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        group = self._require_workspace_group(workspace_id, group_id)
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM document_group_access_grants WHERE doc_id = ? AND group_id = ?",
                (document["id"], group["id"]),
            )
            revoked = cursor.rowcount > 0
            if revoked:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "document.group_access_revoke",
                    target_type="document",
                    target_id=document["id"],
                    details={"group_id": group["id"], "group_name": group["name"]},
                )
        return revoked

    def delete_document(
        self,
        doc_id: str,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> bool:
        doc_id = doc_id.strip()
        if not doc_id:
            raise ValueError("Document id is required.")
        document = self.get_document(doc_id)
        if not document:
            return False
        if workspace_id and document["workspace_id"] != workspace_id:
            return False
        self._require_document_write(document, actor_user_id)
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM documents WHERE id = ?",
                (doc_id,),
            )
            deleted = cursor.rowcount > 0
            if deleted and actor_user_id and document["workspace_id"]:
                self._insert_audit_event(
                    document["workspace_id"],
                    actor_user_id,
                    "document.delete",
                    target_type="document",
                    target_id=doc_id,
                    details={"name": document["name"], "kind": document["kind"]},
                )
        return deleted

    def create_conversation(
        self,
        workspace_id: str,
        actor_user_id: str,
        title: str | None = None,
        source_set_id: str | None = None,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        actor_user_id = actor_user_id.strip()
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_WRITE_ROLES)
        auto_title_pending = not (isinstance(title, str) and title.strip())
        title = (title or DEFAULT_CONVERSATION_TITLE).strip() or DEFAULT_CONVERSATION_TITLE
        normalized_source_set_id = _optional_source_set_id(source_set_id)
        normalized_folder_id = _optional_folder_id(folder_id)
        if normalized_source_set_id and normalized_folder_id:
            raise ValueError("Use source_set_id or folder_id, not both")
        if normalized_source_set_id:
            self.resolve_query_source_set_doc_ids(workspace_id, actor_user_id, normalized_source_set_id)
        if normalized_folder_id:
            self.resolve_query_folder_scope(workspace_id, actor_user_id, normalized_folder_id)
        conversation_id = f"conv_{uuid.uuid4().hex}"
        now = _now()
        self.conn.execute(
            """
            INSERT INTO conversations (
              id, workspace_id, created_by, title, auto_title_pending, source_set_id, folder_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                workspace_id,
                actor_user_id,
                title,
                int(auto_title_pending),
                normalized_source_set_id,
                normalized_folder_id,
                now,
                now,
            ),
        )
        self._commit()
        return {
            "id": conversation_id,
            "workspace_id": workspace_id,
            "created_by": actor_user_id,
            "title": title,
            "auto_title_pending": int(auto_title_pending),
            "source_set_id": normalized_source_set_id,
            "folder_id": normalized_folder_id,
            "created_at": now,
            "updated_at": now,
            "archived_at": None,
        }

    def list_conversations(
        self,
        workspace_id: str,
        actor_user_id: str,
        limit: int = 50,
        *,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        actor_user_id = actor_user_id.strip()
        self.require_workspace_access(workspace_id, actor_user_id)
        limit = max(1, min(int(limit), 100))
        rows = self.conn.execute(
            """
            SELECT c.*,
                   COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN conversation_messages m ON m.conversation_id = c.id
            WHERE c.workspace_id = ? AND c.created_by = ? AND (? OR c.archived_at IS NULL)
            GROUP BY c.id
            ORDER BY c.updated_at DESC, c.created_at DESC
            LIMIT ?
            """,
            (workspace_id, actor_user_id, int(include_archived), limit),
        )
        return [self._conversation_with_visible_scope(dict(row), actor_user_id) for row in rows]

    def archive_conversation(
        self,
        conversation_id: str,
        actor_user_id: str,
        *,
        archived: bool = True,
        expected_workspace_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(archived, bool):
            raise ValueError("archived must be a boolean")
        actor_user_id = actor_user_id.strip()
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
            allow_archived=True,
        )
        self.require_workspace_role(conversation["workspace_id"], actor_user_id, WORKSPACE_WRITE_ROLES)
        now = _now()
        next_archived_at = now if archived else None
        with self._atomic():
            self.conn.execute(
                """
                UPDATE conversations
                SET archived_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_archived_at, now, conversation["id"]),
            )
            self._insert_audit_event(
                conversation["workspace_id"],
                actor_user_id,
                "conversation.archive" if archived else "conversation.unarchive",
                target_type="conversation",
                target_id=conversation["id"],
                details={"archived": archived},
            )
        return self._conversation_for_actor(
            conversation["id"],
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
            allow_archived=True,
        )

    def rename_conversation(
        self,
        conversation_id: str,
        actor_user_id: str,
        title: str,
        *,
        expected_workspace_id: str | None = None,
    ) -> dict[str, Any]:
        actor_user_id = actor_user_id.strip()
        if not isinstance(title, str):
            raise ValueError("title is required")
        title = title.strip()
        if not title:
            raise ValueError("title is required")
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )
        self.require_workspace_role(conversation["workspace_id"], actor_user_id, WORKSPACE_WRITE_ROLES)
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                UPDATE conversations
                SET title = ?, auto_title_pending = 0, updated_at = ?
                WHERE id = ?
                """,
                (title, now, conversation["id"]),
            )
            self._insert_audit_event(
                conversation["workspace_id"],
                actor_user_id,
                "conversation.rename",
                target_type="conversation",
                target_id=conversation["id"],
                details={
                    "title_length": len(title),
                    "previous_title_length": len(conversation["title"]),
                },
            )
        return self._conversation_for_actor(
            conversation["id"],
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )

    def update_conversation_scope(
        self,
        conversation_id: str,
        actor_user_id: str,
        *,
        source_set_id: str | None = None,
        folder_id: str | None = None,
        clear_scope: bool = False,
        expected_workspace_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(clear_scope, bool):
            raise ValueError("clear_scope must be a boolean")
        has_source_set = source_set_id is not None
        has_folder = folder_id is not None
        if sum([has_source_set, has_folder, clear_scope]) != 1:
            raise ValueError("choose one conversation scope update")
        actor_user_id = actor_user_id.strip()
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )
        self.require_workspace_role(conversation["workspace_id"], actor_user_id, WORKSPACE_WRITE_ROLES)
        normalized_source_set_id: str | None = None
        normalized_folder_id: str | None = None
        if has_source_set:
            normalized_source_set_id = _optional_source_set_id(source_set_id)
            if not normalized_source_set_id:
                raise ValueError("source_set_id is required")
            self.resolve_query_source_set_doc_ids(conversation["workspace_id"], actor_user_id, normalized_source_set_id)
        elif has_folder:
            normalized_folder_id = _optional_folder_id(folder_id)
            if not normalized_folder_id:
                raise ValueError("folder_id is required")
            self.resolve_query_folder_scope(conversation["workspace_id"], actor_user_id, normalized_folder_id)
        now = _now()
        with self._atomic():
            self.conn.execute(
                """
                UPDATE conversations
                SET source_set_id = ?, folder_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (normalized_source_set_id, normalized_folder_id, now, conversation["id"]),
            )
            self._insert_audit_event(
                conversation["workspace_id"],
                actor_user_id,
                "conversation.scope_update",
                target_type="conversation",
                target_id=conversation["id"],
                details={
                    "source_set_id": normalized_source_set_id,
                    "folder_id": normalized_folder_id,
                    "cleared": clear_scope,
                },
            )
        return self._conversation_for_actor(
            conversation["id"],
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )

    def delete_conversation(
        self,
        conversation_id: str,
        actor_user_id: str,
        *,
        expected_workspace_id: str | None = None,
    ) -> bool:
        actor_user_id = actor_user_id.strip()
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
            allow_archived=True,
        )
        self.require_workspace_role(conversation["workspace_id"], actor_user_id, WORKSPACE_WRITE_ROLES)
        message_count = self.conn.execute(
            "SELECT COUNT(*) AS count FROM conversation_messages WHERE conversation_id = ?",
            (conversation["id"],),
        ).fetchone()["count"]
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation["id"],),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                self._insert_audit_event(
                    conversation["workspace_id"],
                    actor_user_id,
                    "conversation.delete",
                    target_type="conversation",
                    target_id=conversation["id"],
                    details={
                        "message_count": message_count,
                        "was_archived": bool(conversation.get("archived_at")),
                    },
                )
        return deleted

    def list_conversation_messages(
        self,
        conversation_id: str,
        actor_user_id: str,
        limit: int = 100,
        expected_workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )
        limit = max(1, min(int(limit), 500))
        rows = self.conn.execute(
            """
            SELECT *
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (conversation["id"], limit),
        )
        return [dict(row) for row in rows]

    def export_conversation_transcript(
        self,
        conversation_id: str,
        actor_user_id: str,
        *,
        format: str = "jsonl",
        limit: int = 500,
        expected_workspace_id: str | None = None,
    ) -> str:
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )
        limit = max(1, min(int(limit), 1000))
        rows = self.conn.execute(
            """
            SELECT *
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (conversation["id"], limit),
        )
        messages = [dict(row) for row in rows]
        export_format = format.strip().casefold()
        if export_format == "md":
            export_format = "markdown"
        if export_format == "jsonl":
            transcript = _conversation_transcript_jsonl(conversation, messages)
        elif export_format == "markdown":
            transcript = _conversation_transcript_markdown(conversation, messages)
        else:
            raise ValueError("format must be jsonl or markdown")
        self._insert_audit_event(
            conversation["workspace_id"],
            actor_user_id,
            "conversation.export",
            target_type="conversation",
            target_id=conversation["id"],
            details={"format": export_format, "message_count": len(messages)},
        )
        self._commit()
        return transcript

    def create_conversation_share_link(
        self,
        conversation_id: str,
        actor_user_id: str,
        *,
        expected_workspace_id: str | None = None,
        expires_at: str | None = None,
        redact_content: bool = False,
        max_views: int | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(redact_content, bool):
            raise ValueError("redact_content must be a boolean")
        max_views = _normalize_share_max_views(max_views)
        password_salt, password_hash = _share_password_fields(password)
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )
        self.require_workspace_role(conversation["workspace_id"], actor_user_id, WORKSPACE_WRITE_ROLES)
        expires_at = _normalize_expires_at(expires_at)
        token = f"pcs_{secrets.token_urlsafe(32)}"
        share_link_id = f"csl_{uuid.uuid4().hex}"
        created_at = _now()
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO conversation_share_links (
                  id, workspace_id, conversation_id, created_by, token_hash,
                  password_salt, password_hash, redact_content, max_views,
                  created_at, expires_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    share_link_id,
                    conversation["workspace_id"],
                    conversation["id"],
                    actor_user_id.strip(),
                    _hash_token(token),
                    password_salt,
                    password_hash,
                    1 if redact_content else 0,
                    max_views,
                    created_at,
                    expires_at,
                ),
            )
            self._insert_audit_event(
                conversation["workspace_id"],
                actor_user_id,
                "conversation.share_link_create",
                target_type="conversation",
                target_id=conversation["id"],
                details={
                    "share_link_id": share_link_id,
                    "expires_at": expires_at,
                    "redact_content": redact_content,
                    "max_views": max_views,
                    "password_protected": password_hash is not None,
                },
            )
        link = self._conversation_share_link(share_link_id)
        assert link is not None
        link["token"] = token
        return link

    def list_conversation_share_links(
        self,
        conversation_id: str,
        actor_user_id: str,
        *,
        expected_workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
            allow_archived=True,
        )
        rows = self.conn.execute(
            """
            SELECT id, workspace_id, conversation_id, created_by, redact_content, max_views,
                   password_hash IS NOT NULL AS password_protected, view_count, last_viewed_at,
                   created_at, expires_at, revoked_at
            FROM conversation_share_links
            WHERE conversation_id = ?
            ORDER BY created_at DESC, id
            """,
            (conversation["id"],),
        )
        return [_decorate_conversation_share_link(dict(row)) for row in rows]

    def revoke_conversation_share_link(
        self,
        share_link_id: str,
        actor_user_id: str,
        *,
        expected_workspace_id: str | None = None,
    ) -> bool:
        share_link_id = share_link_id.strip()
        if not share_link_id:
            raise ValueError("Share link id is required.")
        link = self._one("SELECT * FROM conversation_share_links WHERE id = ?", (share_link_id,))
        if not link:
            return False
        conversation = self._conversation_for_actor(
            link["conversation_id"],
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
            allow_archived=True,
        )
        if link["workspace_id"] != conversation["workspace_id"]:
            return False
        if link["revoked_at"] is not None:
            return False
        revoked_at = _now()
        with self._atomic():
            self.conn.execute(
                "UPDATE conversation_share_links SET revoked_at = ? WHERE id = ?",
                (revoked_at, share_link_id),
            )
            self._insert_audit_event(
                conversation["workspace_id"],
                actor_user_id,
                "conversation.share_link_revoke",
                target_type="conversation",
                target_id=conversation["id"],
                details={"share_link_id": share_link_id},
            )
        return True

    def record_conversation_share_link_view(
        self,
        token: str,
        *,
        password: str | None = None,
        response_format: str,
        limit: int,
    ) -> bool:
        token = token.strip()
        if not token:
            raise ValueError("Share token is required.")
        token_hash = _hash_token(token)
        row = self._one(
            """
            SELECT l.id, l.workspace_id, l.conversation_id, l.token_hash, l.redact_content,
                   l.password_salt, l.password_hash, l.expires_at, l.revoked_at, c.archived_at
            FROM conversation_share_links l
            JOIN conversations c ON c.id = l.conversation_id
            WHERE l.token_hash = ?
            """,
            (token_hash,),
        )
        if not row or not hmac.compare_digest(row["token_hash"], token_hash):
            return False
        if not _share_password_matches(password, row["password_salt"], row["password_hash"]):
            return False
        if row["revoked_at"] is not None or _is_expired(row["expires_at"]) or row["archived_at"] is not None:
            return False
        viewed_at = _now()
        with self._atomic():
            cursor = self.conn.execute(
                """
                UPDATE conversation_share_links
                SET view_count = view_count + 1, last_viewed_at = ?
                WHERE id = ?
                  AND revoked_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                  AND (max_views IS NULL OR view_count < max_views)
                  AND EXISTS (
                    SELECT 1 FROM conversations c
                    WHERE c.id = conversation_share_links.conversation_id
                      AND c.archived_at IS NULL
                  )
                """,
                (viewed_at, row["id"], viewed_at),
            )
            if cursor.rowcount != 1:
                return False
            self._insert_audit_event(
                row["workspace_id"],
                "public",
                "conversation.share_link_view",
                target_type="conversation",
                target_id=row["conversation_id"],
                details={
                    "share_link_id": row["id"],
                    "response_format": response_format,
                    "redact_content": bool(row["redact_content"]),
                    "limit": limit,
                },
            )
        return True

    def resolve_conversation_share_link(
        self,
        token: str,
        *,
        password: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any] | None:
        token = token.strip()
        if not token:
            raise ValueError("Share token is required.")
        token_hash = _hash_token(token)
        row = self._one(
            """
            SELECT l.id AS share_link_id, l.workspace_id, l.conversation_id, l.created_by,
                   l.token_hash, l.password_salt, l.password_hash,
                   l.redact_content, l.max_views, l.view_count,
                   l.created_at, l.expires_at, l.revoked_at,
                   c.title, c.created_at AS conversation_created_at, c.updated_at, c.archived_at
            FROM conversation_share_links l
            JOIN conversations c ON c.id = l.conversation_id
            WHERE l.token_hash = ?
            """,
            (token_hash,),
        )
        if not row or not hmac.compare_digest(row["token_hash"], token_hash):
            return None
        if not _share_password_matches(password, row["password_salt"], row["password_hash"]):
            return None
        if row["revoked_at"] is not None or _is_expired(row["expires_at"]) or row["archived_at"] is not None:
            return None
        if _share_link_view_limit_reached(row["view_count"], row["max_views"]):
            return None
        limit = max(1, min(int(limit), 500))
        redact_content = bool(row["redact_content"])
        messages = [
            {
                "id": message["id"],
                "role": message["role"],
                "content": _redact_public_share_text(message["content"])
                if redact_content
                else message["content"],
                "run_id": message["run_id"],
                "created_at": message["created_at"],
            }
            for message in self.conn.execute(
                """
                SELECT id, role, content, run_id, created_at
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (row["conversation_id"], limit),
            )
        ]
        run_ids = [message["run_id"] for message in messages if message.get("run_id")]
        public_run_ids = (
            {run_id: f"public_run_{index}" for index, run_id in enumerate(run_ids, start=1)}
            if redact_content
            else {}
        )
        if redact_content:
            for message in messages:
                message.pop("id", None)
                if message.get("run_id"):
                    message["run_id"] = public_run_ids[message["run_id"]]
        citations_by_run: dict[str, list[dict[str, Any]]] = {
            public_run_ids.get(run_id, run_id): [] for run_id in run_ids
        }
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            for citation in self.conn.execute(
                f"""
                SELECT c.id, c.run_id, c.evidence_id, c.doc_id, d.name AS doc_name,
                       c.label, c.page_start, c.page_end, c.line_start, c.line_end, c.created_at
                FROM citations c
                JOIN documents d ON d.id = c.doc_id
                WHERE c.run_id IN ({placeholders})
                ORDER BY c.created_at, c.id
                """,
                tuple(run_ids),
            ):
                citation_key = public_run_ids.get(citation["run_id"], citation["run_id"])
                citation_payload = dict(citation)
                if redact_content:
                    citation_payload = _redact_conversation_share_citation(citation_payload)
                    for key in ("id", "doc_id", "evidence_id"):
                        citation_payload.pop(key, None)
                    citation_payload["run_id"] = citation_key
                citations_by_run.setdefault(citation_key, []).append(citation_payload)
        share_link = _decorate_conversation_share_link(
            {
                "id": row["share_link_id"],
                "workspace_id": row["workspace_id"],
                "conversation_id": row["conversation_id"],
                "created_by": row["created_by"],
                "redact_content": row["redact_content"],
                "max_views": row["max_views"],
                "password_protected": row["password_hash"] is not None,
                "view_count": row["view_count"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "revoked_at": row["revoked_at"],
            }
        )
        share_link = _strip_public_share_link_management_fields(share_link)
        conversation = {
            "id": row["conversation_id"],
            "workspace_id": row["workspace_id"],
            "title": _redact_public_share_text(row["title"]) if redact_content else row["title"],
            "created_at": row["conversation_created_at"],
            "updated_at": row["updated_at"],
        }
        if redact_content:
            share_link = _minimize_redacted_public_share_link(share_link, "conversation_id")
            conversation = _minimize_redacted_public_entity(conversation, ("id", "workspace_id"))
        return {
            "share_link": share_link,
            "conversation": conversation,
            "messages": messages,
            "citations": citations_by_run,
        }

    def chat_message(
        self,
        conversation_id: str,
        actor_user_id: str,
        message: str,
        *,
        doc_ids: list[str] | None = None,
        expert_hints: list[str] | None = None,
        limit: int = 8,
        expected_workspace_id: str | None = None,
    ) -> dict[str, Any]:
        actor_user_id = actor_user_id.strip()
        message = message.strip()
        if not message:
            raise ValueError("message is required")
        if len(message) > MAX_CONVERSATION_MESSAGE_CHARS:
            raise ValueError("message is too large")
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )
        self.require_workspace_role(conversation["workspace_id"], actor_user_id, WORKSPACE_WRITE_ROLES)
        history_rows = self.conn.execute(
            """
            SELECT content
            FROM conversation_messages
            WHERE conversation_id = ? AND role = 'user'
            ORDER BY created_at DESC, id DESC
            LIMIT 3
            """,
            (conversation["id"],),
        ).fetchall()
        history = [row["content"] for row in reversed(history_rows)]
        retrieval_query = _conversation_query_text(message, history)
        now = _now()
        user_message = {
            "id": f"msg_{uuid.uuid4().hex}",
            "conversation_id": conversation["id"],
            "workspace_id": conversation["workspace_id"],
            "user_id": actor_user_id,
            "role": "user",
            "content": message,
            "run_id": None,
            "created_at": now,
        }
        with self._atomic():
            self.conn.execute(
                """
                INSERT INTO conversation_messages
                  (id, conversation_id, workspace_id, user_id, role, content, run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_message["id"],
                    user_message["conversation_id"],
                    user_message["workspace_id"],
                    user_message["user_id"],
                    user_message["role"],
                    user_message["content"],
                    user_message["run_id"],
                    user_message["created_at"],
                ),
            )
            source_set_id = conversation.get("source_set_id") if doc_ids is None else None
            folder_id = conversation.get("folder_id") if doc_ids is None and not source_set_id else None
            result = self.query_corpus(
                retrieval_query,
                doc_ids=doc_ids,
                source_set_id=source_set_id,
                folder_id=folder_id,
                expert_hints=expert_hints,
                workspace_id=conversation["workspace_id"],
                limit=limit,
                actor_user_id=actor_user_id,
                scope_extra={
                    "conversation": {
                        "id": conversation["id"],
                        "user_message_id": user_message["id"],
                        "history_user_message_count": len(history),
                    }
                },
                stored_query=CHAT_TRACE_QUERY,
                redact_query_tree=True,
            )
            assistant_message = {
                "id": f"msg_{uuid.uuid4().hex}",
                "conversation_id": conversation["id"],
                "workspace_id": conversation["workspace_id"],
                "user_id": actor_user_id,
                "role": "assistant",
                "content": result["answer"],
                "run_id": result["run_id"],
                "created_at": _now(),
            }
            self.conn.execute(
                """
                INSERT INTO conversation_messages
                  (id, conversation_id, workspace_id, user_id, role, content, run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assistant_message["id"],
                    assistant_message["conversation_id"],
                    assistant_message["workspace_id"],
                    assistant_message["user_id"],
                    assistant_message["role"],
                    assistant_message["content"],
                    assistant_message["run_id"],
                    assistant_message["created_at"],
                ),
            )
            generated_title = (
                _conversation_generated_title(message)
                if not history and bool(conversation.get("auto_title_pending"))
                else conversation["title"]
            )
            self.conn.execute(
                "UPDATE conversations SET title = ?, auto_title_pending = 0, updated_at = ? WHERE id = ?",
                (generated_title, assistant_message["created_at"], conversation["id"]),
            )
            conversation["title"] = generated_title
            conversation["auto_title_pending"] = 0
            conversation["updated_at"] = assistant_message["created_at"]
        return {
            "conversation": conversation,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "retrieval": {
                "query": retrieval_query,
                "history_user_messages": history,
            },
            "result": result,
        }

    def _prepare_chat_message(
        self,
        conversation_id: str,
        actor_user_id: str,
        message: str,
        *,
        doc_ids: list[str] | None = None,
        expert_hints: list[str] | None = None,
        limit: int = 8,
        expected_workspace_id: str | None = None,
    ) -> dict[str, Any]:
        actor_user_id = actor_user_id.strip()
        message = message.strip()
        if not message:
            raise ValueError("message is required")
        if len(message) > MAX_CONVERSATION_MESSAGE_CHARS:
            raise ValueError("message is too large")
        conversation = self._conversation_for_actor(
            conversation_id,
            actor_user_id,
            expected_workspace_id=expected_workspace_id,
        )
        self.require_workspace_role(conversation["workspace_id"], actor_user_id, WORKSPACE_WRITE_ROLES)
        history_rows = self.conn.execute(
            """
            SELECT content
            FROM conversation_messages
            WHERE conversation_id = ? AND role = 'user'
            ORDER BY created_at DESC, id DESC
            LIMIT 3
            """,
            (conversation["id"],),
        ).fetchall()
        history = [row["content"] for row in reversed(history_rows)]
        retrieval_query = _conversation_query_text(message, history)
        user_message = {
            "id": f"msg_{uuid.uuid4().hex}",
            "conversation_id": conversation["id"],
            "workspace_id": conversation["workspace_id"],
            "user_id": actor_user_id,
            "role": "user",
            "content": message,
            "run_id": None,
        }
        source_set_id = conversation.get("source_set_id") if doc_ids is None else None
        folder_id = conversation.get("folder_id") if doc_ids is None and not source_set_id else None
        result = self.query_corpus(
            retrieval_query,
            doc_ids=doc_ids,
            source_set_id=source_set_id,
            folder_id=folder_id,
            expert_hints=expert_hints,
            workspace_id=conversation["workspace_id"],
            limit=limit,
            actor_user_id=actor_user_id,
            scope_extra={
                "conversation": {
                    "id": conversation["id"],
                    "user_message_id": user_message["id"],
                    "history_user_message_count": len(history),
                }
            },
            stored_query=CHAT_TRACE_QUERY,
            redact_query_tree=True,
        )
        return {
            "conversation": conversation,
            "user_message": user_message,
            "retrieval": {
                "query": retrieval_query,
                "history_user_messages": history,
            },
            "result": result,
        }

    def _complete_prepared_chat_message(self, prepared: dict[str, Any], assistant_content: str) -> dict[str, Any]:
        assistant_content = assistant_content.strip()
        if not assistant_content:
            raise ValueError("assistant message is required")
        prepared_conversation = dict(prepared["conversation"])
        user_message = dict(prepared["user_message"])
        result = prepared["result"]
        if user_message["conversation_id"] != prepared_conversation["id"]:
            raise ValueError("prepared conversation mismatch")
        if user_message["workspace_id"] != prepared_conversation["workspace_id"]:
            raise ValueError("prepared workspace mismatch")
        with self._atomic():
            conversation = self._conversation_for_actor(
                prepared_conversation["id"],
                user_message["user_id"],
                expected_workspace_id=user_message["workspace_id"],
            )
            self.require_workspace_role(conversation["workspace_id"], user_message["user_id"], WORKSPACE_WRITE_ROLES)
            user_created_at = _now()
            user_message["created_at"] = user_created_at
            assistant_message = {
                "id": f"msg_{uuid.uuid4().hex}",
                "conversation_id": conversation["id"],
                "workspace_id": conversation["workspace_id"],
                "user_id": user_message["user_id"],
                "role": "assistant",
                "content": assistant_content,
                "run_id": result["run_id"],
                "created_at": _now(),
            }
            self.conn.execute(
                """
                INSERT INTO conversation_messages
                  (id, conversation_id, workspace_id, user_id, role, content, run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_message["id"],
                    user_message["conversation_id"],
                    user_message["workspace_id"],
                    user_message["user_id"],
                    user_message["role"],
                    user_message["content"],
                    user_message["run_id"],
                    user_created_at,
                ),
            )
            self.conn.execute(
                """
                INSERT INTO conversation_messages
                  (id, conversation_id, workspace_id, user_id, role, content, run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assistant_message["id"],
                    assistant_message["conversation_id"],
                    assistant_message["workspace_id"],
                    assistant_message["user_id"],
                    assistant_message["role"],
                    assistant_message["content"],
                    assistant_message["run_id"],
                    assistant_message["created_at"],
                ),
            )
            generated_title = _conversation_generated_title(user_message["content"])
            cursor = self.conn.execute(
                """
                UPDATE conversations
                SET title = CASE
                      WHEN auto_title_pending = 1
                       AND NOT EXISTS (
                         SELECT 1
                         FROM conversation_messages
                         WHERE conversation_id = ?
                           AND role = 'user'
                           AND id <> ?
                       )
                      THEN ?
                      ELSE title
                    END,
                    auto_title_pending = 0,
                    updated_at = ?
                WHERE id = ?
                  AND archived_at IS NULL
                """,
                (
                    conversation["id"],
                    user_message["id"],
                    generated_title,
                    assistant_message["created_at"],
                    conversation["id"],
                ),
            )
            if cursor.rowcount != 1:
                raise PermissionError("conversation archived")
            conversation = self._conversation_for_actor(
                conversation["id"],
                user_message["user_id"],
                expected_workspace_id=user_message["workspace_id"],
            )
        return {
            "conversation": conversation,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "retrieval": prepared["retrieval"],
            "result": result,
        }

    def search_documents(
        self,
        query: str,
        limit: int = 20,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        terms = [t.casefold() for t in query.split() if t.strip()]
        if not terms:
            return []
        haystack_sql = "lower(d.name || ' ' || d.description || ' ' || d.source_path)"
        where = " AND ".join([f"{haystack_sql} LIKE ? ESCAPE '\\'" for _ in terms])
        patterns = [f"%{_escape_like(term)}%" for term in terms]
        read_condition, read_args = self._document_read_condition("d", actor_user_id)
        where = f"({where}) AND {read_condition}"
        patterns.extend(read_args)
        if workspace_id:
            where = f"d.workspace_id = ? AND {where}"
            patterns.insert(0, workspace_id)
        rows = self.conn.execute(
            f"SELECT d.* FROM documents d WHERE {where}",
            patterns,
        )
        scored = []
        for row in rows:
            doc = dict(row)
            haystack = f"{doc['name']} {doc['description']} {doc['source_path']}".casefold()
            doc["score"] = sum(haystack.count(term) for term in terms)
            scored.append(doc)
        scored.sort(key=lambda d: (-d["score"], d["name"]))
        return scored[:limit]

    def retrieve_pages(
        self,
        query: str,
        *,
        doc_ids: list[str] | None = None,
        expert_hints: list[str] | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        terms = _terms_for(query, expert_hints)
        if not terms:
            return []
        if doc_ids is not None and not doc_ids:
            return []
        haystack_sql = "lower(d.name || ' ' || d.description || ' ' || p.content)"
        term_where = " OR ".join([f"{haystack_sql} LIKE ? ESCAPE '\\'" for _ in terms])
        args: list[Any] = [f"%{_escape_like(term)}%" for term in terms]
        where_parts = [f"({term_where})"]
        if doc_ids is not None:
            where_parts.append(f"d.id IN ({','.join('?' for _ in doc_ids)})")
            args.extend(doc_ids)
        if workspace_id:
            where_parts.append("d.workspace_id = ?")
            args.append(workspace_id)
        read_condition, read_args = self._document_read_condition("d", actor_user_id)
        where_parts.append(read_condition)
        args.extend(read_args)
        rows = self.conn.execute(
            f"""
            SELECT d.id AS doc_id, d.name AS doc_name, d.page_count, p.page, p.content
            FROM document_pages p
            JOIN documents d ON d.id = p.doc_id
            WHERE {' AND '.join(where_parts)}
            """,
            args,
        )
        hits = []
        for row in rows:
            hit = dict(row)
            haystack = f"{hit['doc_name']} {hit['content']}".casefold()
            hit["score"] = sum(haystack.count(term) for term in terms)
            if hit["score"]:
                line_range = _matching_line_range(hit["content"], terms)
                hit["line_start"] = line_range[0] if line_range else None
                hit["line_end"] = line_range[1] if line_range else None
                hits.append(hit)
        hits.sort(key=lambda h: (-h["score"], h["doc_name"], h["page"]))
        return hits[:limit]

    def query_corpus(
        self,
        query: str,
        *,
        doc_ids: list[str] | None = None,
        source_set_id: str | None = None,
        folder_id: str | None = None,
        expert_hints: list[str] | None = None,
        workspace_id: str | None = None,
        limit: int = 8,
        actor_user_id: str | None = None,
        scope_extra: dict[str, Any] | None = None,
        stored_query: str | None = None,
        redact_query_tree: bool = False,
    ) -> dict[str, Any]:
        if actor_user_id and workspace_id:
            self.require_workspace_access(workspace_id, actor_user_id)
        if doc_ids and source_set_id:
            raise ValueError("Use doc_ids or source_set_id, not both.")
        if source_set_id is not None and not isinstance(source_set_id, str):
            raise ValueError("source_set_id must be a string")
        if folder_id is not None and not isinstance(folder_id, str):
            raise ValueError("folder_id must be a string")
        resolved_source_set_id = source_set_id.strip() if isinstance(source_set_id, str) else None
        resolved_folder_id = folder_id.strip() if isinstance(folder_id, str) else None
        if resolved_folder_id and (doc_ids is not None or resolved_source_set_id):
            raise ValueError("Use only one of doc_ids, source_set_id, or folder_id.")
        source_set_scope: dict[str, Any] | None = None
        folder_scope: dict[str, Any] | None = None
        if resolved_source_set_id:
            if not workspace_id or not actor_user_id:
                raise ValueError("source_set_id requires workspace_id and actor_user_id")
            doc_ids = self.resolve_query_source_set_doc_ids(workspace_id, actor_user_id, resolved_source_set_id)
            source_set_scope = {
                "source_set_id": resolved_source_set_id,
                "source_set_document_count": len(doc_ids),
            }
        elif resolved_folder_id:
            if not workspace_id or not actor_user_id:
                raise ValueError("folder_id requires workspace_id and actor_user_id")
            resolved_folder_scope = self.resolve_query_folder_scope(workspace_id, actor_user_id, resolved_folder_id)
            doc_ids = resolved_folder_scope["doc_ids"]
            folder_scope = {
                "folder_id": resolved_folder_scope["folder_id"],
                "folder_path": resolved_folder_scope["folder_path"],
                "folder_document_count": resolved_folder_scope["folder_document_count"],
            }
        search = self.hybrid_search(
            query,
            doc_ids=doc_ids,
            expert_hints=expert_hints,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            limit=limit,
        )
        with self._atomic():
            query_tree = search["query_tree"]
            if redact_query_tree:
                query_tree = {**query_tree, "query": CHAT_TRACE_QUERY}
            scope = {
                "doc_ids": doc_ids or [],
                "workspace_id": workspace_id,
                "expert_hints": search["expert_hints"],
                "hint_safety": search["hint_safety"],
                "query_tree": query_tree,
                "hybrid_policy": search["policy"],
            }
            if source_set_scope:
                scope.update(source_set_scope)
            if folder_scope:
                scope.update(folder_scope)
            if scope_extra:
                scope.update(scope_extra)
            run_id = self.start_query(
                stored_query or query,
                scope,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
            )
            hits = search["hits"]
            citations = []
            for hit in hits:
                evidence_id = self.add_evidence(
                    run_id=run_id,
                    doc_id=hit["doc_id"],
                    node_id=hit["node_id"],
                    page_start=hit["page_start"],
                    page_end=hit["page_end"],
                    line_start=hit.get("line_start"),
                    line_end=hit.get("line_end"),
                    text=hit["content"],
                    reason=hit["reason"],
                    score=hit["score"],
                )
                citations.append(self.add_citation(run_id=run_id, evidence_id=evidence_id))
            self.finish_query(run_id)
            trace = self.get_trace(run_id)
            verification = self.verify_trace(run_id)
            if actor_user_id and workspace_id:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "query.run",
                    target_type="query_run",
                    target_id=run_id,
                    details={"citation_count": len(citations), "evidence_count": len(hits)},
                )
        return {
            "run_id": run_id,
            "answer": _synthesize_answer(hits),
            "citations": citations,
            "query_tree": search["query_tree"],
            "hybrid_search": search,
            "trace": trace,
            "verification": verification,
        }

    def import_pageindex_structure(
        self,
        structure_path: str | Path,
        *,
        doc_id: str | None = None,
        folder_id: str | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> str:
        path = Path(structure_path).expanduser().resolve()
        self.require_workspace_write(workspace_id, actor_user_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        structure = data.get("structure")
        if not isinstance(structure, list):
            raise ValueError("PageIndex structure JSON must contain a list field named 'structure'.")
        doc_name = str(data.get("doc_name") or path.stem).strip()
        description = str(data.get("doc_description") or "").strip()
        page_count = _max_end_index(structure)
        existing_doc_id = doc_id.strip() if doc_id else None
        existing = self.get_document(existing_doc_id) if existing_doc_id else None
        if existing and existing["workspace_id"] and existing["workspace_id"] != workspace_id:
            raise ValueError("Document belongs to another workspace.")
        with self._atomic():
            if existing:
                self._purge_document_index(existing["id"])
            doc_id = self.register_document(
                doc_id=doc_id,
                name=doc_name,
                source_path=str(path),
                kind=_kind_for(Path(doc_name)),
                description=description,
                folder_id=folder_id,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                page_count=page_count,
            )
            self.conn.execute("DELETE FROM virtual_nodes WHERE axis = 'section' AND doc_id = ?", (doc_id,))
            root_id = self._ensure_virtual_node(
                axis="section",
                label=doc_name,
                path=f"/virtual/doc/{doc_id}",
                summary=description,
                doc_id=doc_id,
                source_node_id="root",
                page_start=1 if page_count else None,
                page_end=page_count,
            )
            self._attach_virtual_doc(root_id, doc_id, "document root", 1.0)
            self._import_structure_nodes(doc_id, structure, root_id, f"/virtual/doc/{doc_id}", ())
            self._commit()
            if actor_user_id and workspace_id:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "document.import_structure",
                    target_type="document",
                    target_id=doc_id,
                    details={"name": doc_name},
                )
        return doc_id

    def rebuild_virtual_index(self) -> None:
        self._delete_virtual_axis("kind")
        self._delete_virtual_axis("folder")
        docs = self.list_documents(limit=100000)
        folders = {row["id"]: row["path"] for row in self.conn.execute("SELECT id, path FROM folders")}
        kind_root = self._ensure_virtual_node(axis="kind", label="By kind", path="/virtual/by-kind")
        folder_root = self._ensure_virtual_node(axis="folder", label="By folder", path="/virtual/by-folder")
        for doc in docs:
            kind = doc["kind"] or "unknown"
            kind_node = self._ensure_virtual_node(
                axis="kind",
                label=kind,
                path=f"/virtual/by-kind/{kind}",
                parent_id=kind_root,
                summary=f"Documents with kind {kind}",
            )
            self._attach_virtual_doc(kind_node, doc["id"], f"document kind is {kind}", 1.0)
            folder_path = folders.get(doc["folder_id"], "/root")
            doc_folder_root = folder_root
            virtual_folder_prefix = "/virtual/by-folder"
            if doc["workspace_id"]:
                workspace_root = self._ensure_virtual_node(
                    axis="folder",
                    label=doc["workspace_id"],
                    path=f"/virtual/by-workspace/{doc['workspace_id']}",
                    parent_id=folder_root,
                    summary=f"Workspace {doc['workspace_id']}",
                )
                doc_folder_root = self._ensure_virtual_node(
                    axis="folder",
                    label="By folder",
                    path=f"/virtual/by-workspace/{doc['workspace_id']}/by-folder",
                    parent_id=workspace_root,
                    summary=f"Folders in workspace {doc['workspace_id']}",
                )
                virtual_folder_prefix = f"/virtual/by-workspace/{doc['workspace_id']}/by-folder"
            folder_node = self._ensure_virtual_node(
                axis="folder",
                label=folder_path.rsplit("/", 1)[-1] or "root",
                path=f"{virtual_folder_prefix}{folder_path}",
                parent_id=doc_folder_root,
                summary=f"Documents in folder {folder_path}",
            )
            self._attach_virtual_doc(folder_node, doc["id"], f"document folder is {folder_path}", 1.0)
        self._commit()

    def list_virtual_nodes(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        if workspace_id:
            workspace_root = f"/virtual/by-workspace/{workspace_id}"
            rows = self.conn.execute(
                """
                SELECT n.*, COUNT(DISTINCT d.id) AS doc_count
                FROM virtual_nodes n
                LEFT JOIN virtual_node_docs v ON v.virtual_node_id = n.id
                LEFT JOIN documents d ON d.id = v.doc_id AND d.workspace_id = ?
                LEFT JOIN documents node_doc ON node_doc.id = n.doc_id
                WHERE d.id IS NOT NULL
                   OR node_doc.workspace_id = ?
                   OR n.path = ?
                   OR n.path LIKE ?
                GROUP BY n.id
                ORDER BY n.path
                """,
                (workspace_id, workspace_id, workspace_root, f"{workspace_root}/%"),
            )
            return [dict(row) for row in rows]
        rows = self.conn.execute(
            """
            SELECT n.*, COUNT(v.doc_id) AS doc_count
            FROM virtual_nodes n
            LEFT JOIN virtual_node_docs v ON v.virtual_node_id = n.id
            GROUP BY n.id
            ORDER BY n.path
            """
        )
        return [dict(row) for row in rows]

    def retrieve_nodes(
        self,
        query: str,
        *,
        doc_ids: list[str] | None = None,
        expert_hints: list[str] | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        terms = _terms_for(query, expert_hints)
        if not terms:
            return []
        if doc_ids is not None and not doc_ids:
            return []
        haystack_sql = "lower(n.label || ' ' || n.summary || ' ' || n.path || ' ' || d.name || ' ' || d.description)"
        term_where = " OR ".join([f"{haystack_sql} LIKE ? ESCAPE '\\'" for _ in terms])
        args: list[Any] = [f"%{_escape_like(term)}%" for term in terms]
        where_parts = [
            "n.axis = 'section'",
            "n.source_node_id IS NOT NULL",
            "n.source_node_id != 'root'",
            "n.page_start IS NOT NULL",
            "n.page_end IS NOT NULL",
            f"({term_where})",
        ]
        if doc_ids is not None:
            where_parts.append(f"n.doc_id IN ({','.join('?' for _ in doc_ids)})")
            args.extend(doc_ids)
        if workspace_id:
            where_parts.append("d.workspace_id = ?")
            args.append(workspace_id)
        read_condition, read_args = self._document_read_condition("d", actor_user_id)
        where_parts.append(read_condition)
        args.extend(read_args)
        rows = self.conn.execute(
            f"""
            SELECT
              n.id AS node_id,
              n.doc_id,
              d.name AS doc_name,
              n.source_node_id,
              n.label AS node_label,
              n.summary,
              n.page_start,
              n.page_end,
              n.path
            FROM virtual_nodes n
            JOIN documents d ON d.id = n.doc_id
            WHERE {' AND '.join(where_parts)}
            """,
            args,
        )
        hits = []
        for row in rows:
            hit = dict(row)
            haystack = (
                f"{hit['doc_name']} {hit['node_label']} {hit['summary']} {hit['path']}"
            ).casefold()
            hit["score"] = sum(haystack.count(term) for term in terms)
            if hit["score"]:
                hit["content"] = hit["summary"] or hit["node_label"]
                hit["reason"] = "section-summary retrieval"
                hits.append(hit)
        hits.sort(key=lambda h: (-h["score"], h["doc_name"], h["page_start"], h["node_id"]))
        return hits[:limit]

    def build_query_tree(
        self,
        query: str,
        *,
        doc_ids: list[str] | None = None,
        expert_hints: list[str] | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        hint_safety = _prepare_hints(expert_hints)
        hints = hint_safety["accepted"]
        docs: dict[str, dict[str, Any]] = {}

        def ensure_doc(doc_id: str, doc_name: str, score: float = 0.0) -> dict[str, Any]:
            doc = docs.setdefault(
                doc_id,
                {
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "score": 0.0,
                    "pages": [],
                    "sections": [],
                },
            )
            doc["score"] += score
            return doc

        for hit in self.retrieve_pages(
            query,
            doc_ids=doc_ids,
            expert_hints=hints,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            limit=limit,
        ):
            doc = ensure_doc(hit["doc_id"], hit["doc_name"], hit["score"])
            doc["pages"].append(
                {
                    "page_start": hit["page"],
                    "page_end": hit["page"],
                    "score": hit["score"],
                    "reason": "page-level lexical retrieval",
                }
            )

        for hit in self.retrieve_nodes(
            query,
            doc_ids=doc_ids,
            expert_hints=hints,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            limit=limit,
        ):
            doc = ensure_doc(hit["doc_id"], hit["doc_name"], hit["score"])
            doc["sections"].append(
                {
                    "node_id": hit["node_id"],
                    "source_node_id": hit["source_node_id"],
                    "label": hit["node_label"],
                    "page_start": hit["page_start"],
                    "page_end": hit["page_end"],
                    "score": hit["score"],
                    "reason": "section-summary retrieval",
                }
            )

        documents = sorted(docs.values(), key=lambda doc: (-doc["score"], doc["doc_name"]))[:limit]
        return {
            "query": query,
            "workspace_id": workspace_id,
            "expert_hints": hints,
            "hint_safety": hint_safety,
            "documents": documents,
            "document_count": len(documents),
            "section_count": sum(len(doc["sections"]) for doc in documents),
            "page_count": sum(len(doc["pages"]) for doc in documents),
        }

    def hybrid_search(
        self,
        query: str,
        *,
        doc_ids: list[str] | None = None,
        expert_hints: list[str] | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        limit: int = 8,
    ) -> dict[str, Any]:
        hint_safety = _prepare_hints(expert_hints)
        hints = hint_safety["accepted"]
        query_tree = self.build_query_tree(
            query,
            doc_ids=doc_ids,
            expert_hints=hints,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            limit=limit,
        )
        hits = []

        for hit in self.retrieve_nodes(
            query,
            doc_ids=doc_ids,
            expert_hints=hints,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            limit=limit,
        ):
            hit = dict(hit)
            hit["reason"] = "hybrid section-first retrieval"
            hit["selection_stage"] = "section"
            hits.append(hit)

        section_spans = [
            (hit["doc_id"], hit["page_start"], hit["page_end"])
            for hit in hits
            if hit["page_start"] is not None and hit["page_end"] is not None
        ]
        for hit in self.retrieve_pages(
            query,
            doc_ids=doc_ids,
            expert_hints=hints,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            limit=limit,
        ):
            if len(hits) >= limit:
                break
            if _covered_by_section(hit["doc_id"], hit["page"], section_spans):
                continue
            page_hit = dict(hit)
            page_hit["page_start"] = page_hit["page"]
            page_hit["page_end"] = page_hit["page"]
            page_hit["node_id"] = None
            page_hit["reason"] = "hybrid page fallback retrieval"
            page_hit["selection_stage"] = "page_fallback"
            hits.append(page_hit)

        hits.sort(
            key=lambda h: (
                0 if h["selection_stage"] == "section" else 1,
                -h["score"],
                h["doc_name"],
                h["page_start"],
                h.get("node_id") or "",
            )
        )
        hits = hits[:limit]
        policy = {
            "name": "deterministic-section-first",
            "limit": limit,
            "expert_hints": hints,
            "hint_safety": hint_safety,
            "section_hits": sum(1 for hit in hits if hit["selection_stage"] == "section"),
            "page_fallback_hits": sum(1 for hit in hits if hit["selection_stage"] == "page_fallback"),
        }
        return {
            "query": query,
            "workspace_id": workspace_id,
            "expert_hints": hints,
            "hint_safety": hint_safety,
            "policy": policy,
            "query_tree": query_tree,
            "hits": hits,
        }

    def plan_query_tree(self, query: str, limit: int = 10, workspace_id: str | None = None) -> dict[str, Any]:
        terms = [t.casefold() for t in query.split() if t.strip()]
        nodes = self.list_virtual_nodes(workspace_id=workspace_id)
        scored = []
        for node in nodes:
            haystack = f"{node['axis']} {node['label']} {node['path']} {node['summary']}".casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                node = dict(node)
                node["score"] = score
                scored.append(node)
        if not scored:
            scored = [dict(node, score=0) for node in nodes if node["doc_count"]][:limit]
        scored.sort(key=lambda node: (-node["score"], node["path"]))
        return {"query": query, "workspace_id": workspace_id, "nodes": scored[:limit]}

    def start_query(
        self,
        query: str,
        scope: dict[str, Any] | None = None,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
    ) -> str:
        run_id = f"run_{uuid.uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO query_runs (id, workspace_id, actor_user_id, query, scope_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                workspace_id,
                actor_user_id.strip() if actor_user_id else None,
                query,
                json.dumps(scope or {}, sort_keys=True),
                _now(),
            ),
        )
        self._commit()
        return run_id

    def add_evidence(
        self,
        *,
        run_id: str,
        doc_id: str,
        text: str,
        reason: str,
        node_id: str | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        score: float = 0.0,
    ) -> str:
        if not self._one("SELECT id FROM query_runs WHERE id = ?", (run_id,)):
            raise ValueError(f"Query run not found: {run_id}")
        doc = self.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")
        if page_start is not None or page_end is not None:
            if page_start is None or page_end is None or page_start < 1 or page_end < page_start:
                raise ValueError("Evidence page range is invalid.")
            if doc.get("page_count") and page_end > doc["page_count"]:
                raise ValueError("Evidence page range exceeds document page count.")
        if line_start is not None or line_end is not None:
            if (
                line_start is None
                or line_end is None
                or line_start < 1
                or line_end < line_start
            ):
                raise ValueError("Evidence line range is invalid.")
            if page_start is None or page_end is None:
                raise ValueError("Evidence line range requires a page range.")
            if page_start != page_end:
                raise ValueError("Evidence line range requires single-page evidence.")
            page = self._one(
                "SELECT content FROM document_pages WHERE doc_id = ? AND page = ?",
                (doc_id, page_start),
            )
            if not page:
                raise ValueError("Evidence line range requires stored page text.")
            if line_end > _content_line_count(page["content"]):
                raise ValueError("Evidence line range exceeds page line count.")
        evidence_id = f"ev_{uuid.uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO evidence (
              id, run_id, doc_id, node_id, page_start, page_end,
              line_start, line_end, text, reason, score, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                run_id,
                doc_id,
                node_id,
                page_start,
                page_end,
                line_start,
                line_end,
                text,
                reason,
                score,
                _now(),
            ),
        )
        self._commit()
        return evidence_id

    def add_citation(self, *, run_id: str, evidence_id: str) -> dict[str, Any]:
        evidence = self._one("SELECT * FROM evidence WHERE id = ? AND run_id = ?", (evidence_id, run_id))
        if not evidence:
            raise ValueError(f"Evidence not found for run: {evidence_id}")
        if evidence["page_start"] is None or evidence["page_end"] is None:
            raise ValueError("Citation requires page-backed evidence.")
        doc = self.get_document(evidence["doc_id"])
        if not doc:
            raise ValueError(f"Document not found: {evidence['doc_id']}")
        citation_id = f"cit_{uuid.uuid4().hex}"
        label = f"{doc['name']} p.{evidence['page_start']}"
        if evidence["page_end"] != evidence["page_start"]:
            label = f"{doc['name']} pp.{evidence['page_start']}-{evidence['page_end']}"
        if evidence["line_start"] is not None:
            if evidence["line_start"] == evidence["line_end"]:
                label = f"{label} line {evidence['line_start']}"
            else:
                label = f"{label} lines {evidence['line_start']}-{evidence['line_end']}"
        self.conn.execute(
            """
            INSERT INTO citations (
              id, run_id, evidence_id, doc_id, label, page_start, page_end,
              line_start, line_end, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                citation_id,
                run_id,
                evidence_id,
                evidence["doc_id"],
                label,
                evidence["page_start"],
                evidence["page_end"],
                evidence["line_start"],
                evidence["line_end"],
                _now(),
            ),
        )
        self._commit()
        return {
            "id": citation_id,
            "evidence_id": evidence_id,
            "doc_id": evidence["doc_id"],
            "doc_name": doc["name"],
            "label": label,
            "page_start": evidence["page_start"],
            "page_end": evidence["page_end"],
            "line_start": evidence["line_start"],
            "line_end": evidence["line_end"],
        }

    def finish_query(self, run_id: str) -> None:
        self.conn.execute("UPDATE query_runs SET completed_at = ? WHERE id = ?", (_now(), run_id))
        self._commit()

    def list_query_runs(
        self,
        workspace_id: str,
        actor_user_id: str,
        *,
        limit: int = 50,
        run_actor_user_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        limit = max(1, min(int(limit), 200))
        where = ["q.workspace_id = ?"]
        args: list[Any] = [workspace_id]
        if run_actor_user_id and run_actor_user_id.strip():
            where.append("q.actor_user_id = ?")
            args.append(run_actor_user_id.strip())
        if since and since.strip():
            where.append("q.created_at >= ?")
            args.append(since.strip())
        if until and until.strip():
            where.append("q.created_at <= ?")
            args.append(until.strip())
        if query and query.strip():
            where.append("lower(q.query) LIKE ? ESCAPE '\\'")
            args.append(f"%{_escape_like(query.strip().casefold())}%")
        args.append(limit)
        rows = self.conn.execute(
            f"""
            SELECT q.id, q.workspace_id, q.actor_user_id, q.query, q.scope_json, q.created_at, q.completed_at,
                   COUNT(DISTINCT e.id) AS evidence_count,
                   COUNT(DISTINCT c.id) AS citation_count
            FROM query_runs q
            LEFT JOIN evidence e ON e.run_id = q.id
            LEFT JOIN citations c ON c.run_id = q.id
            WHERE {' AND '.join(where)}
            GROUP BY q.id
            ORDER BY q.created_at DESC, q.id DESC
            LIMIT ?
            """,
            args,
        )
        runs = []
        for row in rows:
            run = dict(row)
            run["scope"] = json.loads(run.pop("scope_json"))
            runs.append(run)
        return runs

    def export_query_runs(
        self,
        workspace_id: str,
        actor_user_id: str,
        limit: int = 500,
        *,
        run_actor_user_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        query: str | None = None,
        format: str = "jsonl",
    ) -> str:
        runs = self.list_query_runs(
            workspace_id,
            actor_user_id,
            limit=limit,
            run_actor_user_id=run_actor_user_id,
            since=since,
            until=until,
            query=query,
        )
        ordered = list(reversed(runs))
        export_format = format.strip().casefold()
        if export_format == "jsonl":
            exported = "\n".join(json.dumps(run, sort_keys=True) for run in ordered)
        elif export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "id",
                    "workspace_id",
                    "actor_user_id",
                    "query",
                    "created_at",
                    "completed_at",
                    "evidence_count",
                    "citation_count",
                    "scope_json",
                ]
            )
            for run in ordered:
                writer.writerow(
                    [
                        run["id"],
                        run["workspace_id"],
                        run["actor_user_id"] or "",
                        run["query"],
                        run["created_at"],
                        run["completed_at"] or "",
                        run["evidence_count"],
                        run["citation_count"],
                        json.dumps(run["scope"], sort_keys=True),
                    ]
                )
            exported = output.getvalue()
        else:
            raise ValueError("format must be jsonl or csv")
        self._insert_audit_event(
            workspace_id,
            actor_user_id,
            "query_runs.export",
            target_type="query_runs",
            target_id=workspace_id,
            details={"format": export_format, "run_count": len(runs)},
        )
        self._commit()
        return exported

    def delete_query_run(self, run_id: str, *, workspace_id: str, actor_user_id: str) -> bool:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        run_id = run_id.strip()
        if not run_id:
            raise ValueError("Query run id is required.")
        with self._atomic():
            cursor = self.conn.execute(
                "DELETE FROM query_runs WHERE id = ? AND workspace_id = ?",
                (run_id, workspace_id),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                self._insert_audit_event(
                    workspace_id,
                    actor_user_id,
                    "query.run_delete",
                    target_type="query_run",
                    target_id=run_id,
                    details={},
                )
        return deleted

    def get_query_trace(self, run_id: str, *, workspace_id: str, actor_user_id: str) -> dict[str, Any] | None:
        self.require_workspace_role(workspace_id, actor_user_id, WORKSPACE_ADMIN_ROLES)
        run_id = run_id.strip()
        if not run_id:
            raise ValueError("Query run id is required.")
        run = self._one("SELECT workspace_id FROM query_runs WHERE id = ?", (run_id,))
        if not run or run["workspace_id"] != workspace_id:
            return None
        return self.get_trace(run_id)

    def get_trace(self, run_id: str) -> dict[str, Any]:
        run = self._one("SELECT * FROM query_runs WHERE id = ?", (run_id,))
        if not run:
            raise ValueError(f"Query run not found: {run_id}")
        evidence = [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM evidence WHERE run_id = ? ORDER BY score DESC, created_at",
                (run_id,),
            )
        ]
        citations = [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM citations WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            )
        ]
        trace = dict(run)
        trace["scope"] = json.loads(trace.pop("scope_json"))
        trace["evidence"] = evidence
        trace["citations"] = citations
        return trace

    def verify_trace(self, run_id: str, *, require_citations: bool = True) -> dict[str, Any]:
        trace = self.get_trace(run_id)
        errors = []
        if trace["completed_at"] is None:
            errors.append("query run is not completed")
        evidence_ids = {ev["id"] for ev in trace["evidence"]}
        cited_evidence_ids = {citation["evidence_id"] for citation in trace["citations"]}
        if require_citations and evidence_ids != cited_evidence_ids:
            missing = sorted(evidence_ids - cited_evidence_ids)
            extra = sorted(cited_evidence_ids - evidence_ids)
            if missing:
                errors.append(f"evidence without citations: {', '.join(missing)}")
            if extra:
                errors.append(f"citations without evidence: {', '.join(extra)}")
        for ev in trace["evidence"]:
            doc = self.get_document(ev["doc_id"])
            if not doc:
                errors.append(f"evidence references missing document {ev['doc_id']}")
                continue
            if ev["page_start"] is None or ev["page_end"] is None:
                errors.append(f"evidence {ev['id']} has no page range")
                continue
            for page in range(ev["page_start"], ev["page_end"] + 1):
                if not self._evidence_page_exists(ev, page):
                    errors.append(f"evidence {ev['id']} references missing page {page}")
            if ev["line_start"] is None and ev["line_end"] is None:
                continue
            if ev["line_start"] is None or ev["line_end"] is None:
                errors.append(f"evidence {ev['id']} has invalid line range")
                continue
            if ev["line_start"] < 1 or ev["line_end"] < ev["line_start"]:
                errors.append(f"evidence {ev['id']} has invalid line range")
                continue
            if ev["page_start"] != ev["page_end"]:
                errors.append(f"evidence {ev['id']} has line range across multiple pages")
                continue
            page = self._one(
                "SELECT content FROM document_pages WHERE doc_id = ? AND page = ?",
                (ev["doc_id"], ev["page_start"]),
            )
            if not page:
                errors.append(f"evidence {ev['id']} has line range without stored page text")
                continue
            if ev["line_end"] > _content_line_count(page["content"]):
                errors.append(f"evidence {ev['id']} line range exceeds page line count")
        for citation in trace["citations"]:
            if citation["evidence_id"] not in evidence_ids:
                errors.append(f"citation {citation['id']} references missing evidence")
            ev = next((item for item in trace["evidence"] if item["id"] == citation["evidence_id"]), None)
            if ev and (
                citation["doc_id"] != ev["doc_id"]
                or citation["page_start"] != ev["page_start"]
                or citation["page_end"] != ev["page_end"]
                or citation["line_start"] != ev["line_start"]
                or citation["line_end"] != ev["line_end"]
            ):
                errors.append(f"citation {citation['id']} does not match evidence {ev['id']}")
        return {"ok": not errors, "errors": errors}

    def _delete_virtual_axis(self, axis: str) -> None:
        self.conn.execute(
            """
            DELETE FROM virtual_node_docs
            WHERE virtual_node_id IN (SELECT id FROM virtual_nodes WHERE axis = ?)
            """,
            (axis,),
        )
        self.conn.execute("DELETE FROM virtual_nodes WHERE axis = ?", (axis,))

    def _evidence_page_exists(self, evidence: dict[str, Any], page: int) -> bool:
        if self._one("SELECT 1 FROM document_pages WHERE doc_id = ? AND page = ?", (evidence["doc_id"], page)):
            return True
        if evidence["node_id"]:
            return bool(
                self._one(
                    """
                    SELECT 1
                    FROM virtual_nodes
                    WHERE id = ?
                      AND doc_id = ?
                      AND page_start <= ?
                      AND page_end >= ?
                    """,
                    (evidence["node_id"], evidence["doc_id"], page, page),
                )
            )
        return False

    def _import_structure_nodes(
        self,
        doc_id: str,
        nodes: list[dict[str, Any]],
        parent_id: str,
        parent_path: str,
        trail: tuple[int, ...],
    ) -> None:
        for index, node in enumerate(nodes, 1):
            if not isinstance(node, dict):
                continue
            source_node_id = str(node.get("node_id") or ".".join(map(str, (*trail, index))))
            page_start = _as_int(node.get("start_index"))
            page_end = _as_int(node.get("end_index"))
            node_id = self._ensure_virtual_node(
                axis="section",
                label=str(node.get("title") or source_node_id),
                path=f"{parent_path}/{_safe_path_part(source_node_id)}",
                parent_id=parent_id,
                summary=str(node.get("summary") or ""),
                doc_id=doc_id,
                source_node_id=source_node_id,
                page_start=page_start,
                page_end=page_end,
            )
            self._attach_virtual_doc(node_id, doc_id, "document section", 1.0)
            children = node.get("nodes") or []
            if isinstance(children, list):
                self._import_structure_nodes(doc_id, children, node_id, f"{parent_path}/{_safe_path_part(source_node_id)}", (*trail, index))

    def _one(self, sql: str, args: tuple[Any, ...]) -> sqlite3.Row | None:
        return self.conn.execute(sql, args).fetchone()

    def _document_share_link(self, share_link_id: str) -> dict[str, Any] | None:
        row = self._one(
            """
            SELECT id, workspace_id, doc_id, created_by, redact_content, max_views,
                   password_hash IS NOT NULL AS password_protected, view_count, last_viewed_at,
                   created_at, expires_at, revoked_at
            FROM document_share_links
            WHERE id = ?
            """,
            (share_link_id,),
        )
        return _decorate_document_share_link(dict(row)) if row else None

    def _conversation_share_link(self, share_link_id: str) -> dict[str, Any] | None:
        row = self._one(
            """
            SELECT id, workspace_id, conversation_id, created_by, redact_content, max_views,
                   password_hash IS NOT NULL AS password_protected, view_count, last_viewed_at,
                   created_at, expires_at, revoked_at
            FROM conversation_share_links
            WHERE id = ?
            """,
            (share_link_id,),
        )
        return _decorate_conversation_share_link(dict(row)) if row else None

    def _ensure_virtual_node(
        self,
        *,
        axis: str,
        label: str,
        path: str,
        summary: str = "",
        parent_id: str | None = None,
        doc_id: str | None = None,
        source_node_id: str | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> str:
        existing = self._one("SELECT id FROM virtual_nodes WHERE path = ?", (path,))
        if existing:
            self.conn.execute(
                """
                UPDATE virtual_nodes
                SET parent_id = ?, doc_id = ?, axis = ?, label = ?, summary = ?,
                    source_node_id = ?, page_start = ?, page_end = ?
                WHERE id = ?
                """,
                (
                    parent_id,
                    doc_id,
                    axis,
                    label,
                    summary,
                    source_node_id,
                    page_start,
                    page_end,
                    existing["id"],
                ),
            )
            return existing["id"]
        node_id = f"vn_{uuid.uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO virtual_nodes (
              id, parent_id, doc_id, axis, label, path, summary,
              source_node_id, page_start, page_end, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (node_id, parent_id, doc_id, axis, label, path, summary, source_node_id, page_start, page_end, _now()),
        )
        return node_id

    def _attach_virtual_doc(self, virtual_node_id: str, doc_id: str, reason: str, score: float) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO virtual_node_docs (virtual_node_id, doc_id, reason, score)
            VALUES (?, ?, ?, ?)
            """,
            (virtual_node_id, doc_id, reason, score),
        )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _clean_hints(expert_hints: list[str] | None) -> list[str]:
    return [hint.strip() for hint in expert_hints or [] if hint.strip()]


def _prepare_hints(expert_hints: list[str] | None) -> dict[str, Any]:
    accepted = []
    rejected = []
    for hint in _clean_hints(expert_hints):
        reason = _unsafe_hint_reason(hint)
        if reason:
            rejected.append({"hint": hint, "reason": reason})
        else:
            accepted.append(hint)
    return {"accepted": accepted, "rejected": rejected}


def _unsafe_hint_reason(hint: str) -> str | None:
    lowered = " ".join(hint.casefold().split())
    unsafe_phrases = [
        "ignore previous",
        "ignore all previous",
        "system prompt",
        "developer message",
        "follow my instructions",
        "do not follow",
        "jailbreak",
        "reveal hidden",
    ]
    if any(phrase in lowered for phrase in unsafe_phrases):
        return "prompt-injection phrase"
    return None


def _terms_for(query: str, expert_hints: list[str] | None = None) -> list[str]:
    text = " ".join([query, *_prepare_hints(expert_hints)["accepted"]])
    return [term.casefold() for term in text.split() if term.strip()]


def _matching_line_range(content: str, terms: list[str]) -> tuple[int, int] | None:
    lowered_terms = [term.casefold() for term in terms if term.strip()]
    if not lowered_terms:
        return None
    matches = []
    for index, line in enumerate(str(content).splitlines() or [str(content)], 1):
        lowered = line.casefold()
        if any(term in lowered for term in lowered_terms):
            matches.append(index)
    if not matches:
        return None
    return matches[0], matches[-1]


def _content_line_count(content: str) -> int:
    return max(1, len(str(content).splitlines()))


def _share_link_view_limit_reached(view_count: Any, max_views: Any) -> bool:
    if max_views is None:
        return False
    return int(view_count or 0) >= int(max_views)


def _share_link_is_active(link: dict[str, Any]) -> bool:
    if link.get("revoked_at") is not None or _is_expired(link.get("expires_at")):
        return False
    return not _share_link_view_limit_reached(link.get("view_count"), link.get("max_views"))


def _decorate_document_share_link(link: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(link)
    decorated["redact_content"] = bool(decorated.get("redact_content"))
    decorated["password_protected"] = bool(decorated.get("password_protected"))
    decorated["max_views"] = int(decorated["max_views"]) if decorated.get("max_views") is not None else None
    decorated["view_count"] = int(decorated.get("view_count") or 0)
    decorated["last_viewed_at"] = decorated.get("last_viewed_at")
    decorated["active"] = _share_link_is_active(decorated)
    return decorated


def _decorate_conversation_share_link(link: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(link)
    decorated["redact_content"] = bool(decorated.get("redact_content"))
    decorated["password_protected"] = bool(decorated.get("password_protected"))
    decorated["max_views"] = int(decorated["max_views"]) if decorated.get("max_views") is not None else None
    decorated["view_count"] = int(decorated.get("view_count") or 0)
    decorated["last_viewed_at"] = decorated.get("last_viewed_at")
    decorated["active"] = _share_link_is_active(decorated)
    return decorated


def _decorate_source_set_share_link(link: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(link)
    decorated["redact_content"] = bool(decorated.get("redact_content"))
    decorated["password_protected"] = bool(decorated.get("password_protected"))
    decorated["max_views"] = int(decorated["max_views"]) if decorated.get("max_views") is not None else None
    decorated["view_count"] = int(decorated.get("view_count") or 0)
    decorated["last_viewed_at"] = decorated.get("last_viewed_at")
    decorated["active"] = _share_link_is_active(decorated)
    return decorated


def _question_subject(name: str) -> str:
    subject = " ".join((name or "this document").split())
    if len(subject) > 80:
        subject = subject[:77].rstrip() + "..."
    return subject or "this document"


def _question_keywords(text: str) -> list[str]:
    counts: dict[str, int] = {}
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text.casefold()):
        token = token.strip("-")
        if not token or token in QUESTION_SUGGESTION_STOPWORDS or token.isdigit():
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token.replace("-", " ") for token, _count in ranked[:8]]


def _kind_for(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "pdf"
    if path.suffix.lower() in {".md", ".markdown"}:
        return "md"
    if path.suffix.lower() == ".txt":
        return "txt"
    return "unknown"


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _max_end_index(nodes: list[dict[str, Any]]) -> int | None:
    maximum = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        end_index = _as_int(node.get("end_index"))
        if end_index:
            maximum = max(maximum, end_index)
        children = node.get("nodes") or []
        if isinstance(children, list):
            child_max = _max_end_index(children)
            if child_max:
                maximum = max(maximum, child_max)
    return maximum or None


def _safe_path_part(value: str) -> str:
    return value.strip().replace("/", "_") or "node"


def _covered_by_section(doc_id: str, page: int, section_spans: list[tuple[str, int, int]]) -> bool:
    return any(span_doc == doc_id and start <= page <= end for span_doc, start, end in section_spans)


def _extract_pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        try:
            import PyPDF2
        except ImportError as exc:
            raise RuntimeError("PDF ingestion requires PyPDF2. Run `python3 -m pip install -r requirements.txt`.") from exc
        with path.open("rb") as f:
            reader = PyPDF2.PdfReader(f)
            return [page.extract_text() or "" for page in reader.pages]
    text = path.read_text(encoding="utf-8")
    if "\f" in text:
        return [part.strip() for part in text.split("\f") if part.strip()]
    lines = text.splitlines()
    return ["\n".join(lines[i : i + 80]).strip() for i in range(0, len(lines), 80)] or [""]


def _summarize_pages(pages: list[str]) -> str:
    joined = " ".join(page.strip().replace("\n", " ") for page in pages if page.strip())
    return joined[:500]


def _synthesize_answer(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "No evidence found."
    docs = []
    seen = set()
    for hit in hits:
        if hit["doc_id"] not in seen:
            page_start = hit.get("page") or hit["page_start"]
            page_end = hit.get("page_end") or page_start
            if page_end == page_start:
                docs.append(f"{hit['doc_name']} p.{page_start}")
            else:
                docs.append(f"{hit['doc_name']} pp.{page_start}-{page_end}")
            seen.add(hit["doc_id"])
    return "Found relevant evidence in " + "; ".join(docs) + "."


def _conversation_transcript_jsonl(conversation: dict[str, Any], messages: list[dict[str, Any]]) -> str:
    lines = [
        json.dumps(
            {
                "type": "conversation",
                "conversation": conversation,
            },
            sort_keys=True,
        )
    ]
    lines.extend(json.dumps({"type": "message", "message": message}, sort_keys=True) for message in messages)
    return "\n".join(lines)


def _conversation_transcript_markdown(conversation: dict[str, Any], messages: list[dict[str, Any]]) -> str:
    lines = [
        f"# {_markdown_inline_text(conversation['title'])}",
        "",
        f"- Conversation ID: `{conversation['id']}`",
        f"- Workspace ID: `{conversation['workspace_id']}`",
        f"- Created by: `{conversation['created_by']}`",
        f"- Created at: `{conversation['created_at']}`",
        f"- Updated at: `{conversation['updated_at']}`",
        "",
    ]
    for message in messages:
        role = str(message["role"]).capitalize()
        lines.extend([f"## {role} - {message['created_at']}", "", _markdown_fence(message["content"]), ""])
        if message.get("run_id"):
            lines.extend([f"Run ID: `{message['run_id']}`", ""])
    return "\n".join(lines).rstrip() + "\n"


def _markdown_inline_text(value: str) -> str:
    normalized = " ".join(str(value).splitlines()).replace("`", "'").strip() or "Conversation"
    escaped = html.escape(normalized, quote=False)
    return re.sub(r"([\\\[\]\(\)*_{}#+\-.!|])", r"\\\1", escaped)


def _markdown_fence(value: str) -> str:
    content = str(value).replace("\r\n", "\n").replace("\r", "\n")
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}text\n{content}\n{fence}"


def _conversation_query_text(message: str, history: list[str]) -> str:
    parts = [part.strip() for part in [*history[-3:], message] if part and part.strip()]
    return " ".join(parts)[-2000:]


def _conversation_generated_title(message: str) -> str:
    title = " ".join(str(message).split()).strip(" \t\r\n.,;:!?")
    if not title:
        return DEFAULT_CONVERSATION_TITLE
    title = title[:1].upper() + title[1:]
    if len(title) <= MAX_CONVERSATION_TITLE_CHARS:
        return title
    truncated = title[:MAX_CONVERSATION_TITLE_CHARS].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0].rstrip(".,;:!?")
    return truncated or title[:MAX_CONVERSATION_TITLE_CHARS].rstrip(".,;:!?")
