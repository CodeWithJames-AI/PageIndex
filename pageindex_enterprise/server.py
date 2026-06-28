from __future__ import annotations

import json
import threading
import time
import uuid
from email.parser import BytesParser
from email.policy import default
from html import escape as html_escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .dashboard import DASHBOARD_HTML
from .deployment import run_deployment_check
from .llm import LLMProviderError, open_openai_compatible_stream, synthesize_with_openai_compatible
from .store import (
    API_TOKEN_SCOPES,
    CHAT_TRACE_QUERY,
    WORKSPACE_ADMIN_ROLES,
    WORKSPACE_WRITE_ROLES,
    EnterpriseStore,
    _UNSET,
    _redacted_audit_export_events,
    expires_at_from_days,
)


MAX_JSON_BODY_BYTES = 64 * 1024
MAX_MULTIPART_BODY_BYTES = 10 * 1024 * 1024
MAX_MULTIPART_FILES = 20


class RateLimitError(Exception):
    def __init__(self, retry_after_seconds: int):
        super().__init__("api token rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class EnterpriseHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        root: str | Path,
        *,
        require_api_token: bool = False,
        api_token_rate_limit: int | None = None,
        api_token_rate_window_seconds: float = 60.0,
    ):
        super().__init__(server_address, EnterpriseHandler)
        if api_token_rate_limit is not None and api_token_rate_limit <= 0:
            raise ValueError("api_token_rate_limit must be positive")
        if api_token_rate_window_seconds <= 0:
            raise ValueError("api_token_rate_window_seconds must be positive")
        self.root = root
        self.require_api_token = require_api_token
        self.api_token_rate_limit = api_token_rate_limit
        self.api_token_rate_window_seconds = float(api_token_rate_window_seconds)
        self._api_token_rate_windows: dict[str, tuple[float, int]] = {}
        self._api_token_rate_lock = threading.Lock()

    def check_api_token_rate_limit(self, token_id: str) -> None:
        if self.api_token_rate_limit is None:
            return
        now = time.monotonic()
        with self._api_token_rate_lock:
            started_at, count = self._api_token_rate_windows.get(token_id, (now, 0))
            elapsed = now - started_at
            if elapsed >= self.api_token_rate_window_seconds:
                started_at, count = now, 0
                elapsed = 0
            if count >= self.api_token_rate_limit:
                remaining = self.api_token_rate_window_seconds - elapsed
                raise RateLimitError(max(1, int(remaining + 0.999)))
            self._api_token_rate_windows[token_id] = (started_at, count + 1)


class EnterpriseHandler(BaseHTTPRequestHandler):
    server: EnterpriseHTTPServer

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._json({"ok": True})
                return
            public_document_share_token = _public_document_share_path(parsed.path)
            if public_document_share_token:
                self._public_document_share(public_document_share_token, parsed.query)
                return
            public_conversation_share_token = _public_conversation_share_path(parsed.path)
            if public_conversation_share_token:
                self._public_conversation_share(public_conversation_share_token, parsed.query)
                return
            public_source_set_share_token = _public_source_set_share_path(parsed.path)
            if public_source_set_share_token:
                self._public_source_set_share(public_source_set_share_token, parsed.query)
                return
            if parsed.path in {"/", "/dashboard"}:
                self._html(DASHBOARD_HTML)
                return
            if parsed.path == "/conversations":
                params = parse_qs(parsed.query)
                limit = _int_param(params, "limit", 50)
                include_archived = _bool_param(params, "include_archived", False)
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="read")
                    self._json(
                        {
                            "conversations": store.list_conversations(
                                workspace_id,
                                user_id,
                                limit=limit,
                                include_archived=include_archived,
                            )
                        }
                    )
                finally:
                    store.close()
                return
            conversation_export_id = _conversation_export_path(parsed.path)
            if conversation_export_id:
                params = parse_qs(parsed.query)
                export_format = _str_param(params, "format", "jsonl")
                limit = _int_param(params, "limit", 500)
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="read")
                    exported = store.export_conversation_transcript(
                        conversation_export_id,
                        user_id,
                        format=export_format,
                        limit=limit,
                        expected_workspace_id=workspace_id,
                    )
                    content_type = (
                        "text/markdown; charset=utf-8"
                        if (export_format or "jsonl").strip().casefold() in {"markdown", "md"}
                        else "application/x-ndjson; charset=utf-8"
                    )
                    self._text(exported, content_type=content_type)
                finally:
                    store.close()
                return
            conversation_id = _conversation_messages_path(parsed.path)
            if conversation_id:
                params = parse_qs(parsed.query)
                limit = _int_param(params, "limit", 100)
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="read")
                    self._json(
                        {
                            "messages": store.list_conversation_messages(
                                conversation_id,
                                user_id,
                                limit=limit,
                                expected_workspace_id=workspace_id,
                            )
                        }
                    )
                finally:
                    store.close()
                return
            conversation_share_links_id = _conversation_share_links_path(parsed.path)
            if conversation_share_links_id:
                self._list_conversation_share_links(conversation_share_links_id)
                return
            if parsed.path == "/audit-events/export":
                params = parse_qs(parsed.query)
                limit = _int_param(params, "limit", 500)
                export_format = _str_param(params, "format", "jsonl")
                export_format_name = (export_format or "jsonl").strip().casefold()
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit")
                    exported = store.export_audit_events(
                        workspace_id,
                        user_id,
                        limit=limit,
                        since=_str_param(params, "since"),
                        until=_str_param(params, "until"),
                        action=_str_param(params, "action"),
                        event_user_id=_str_param(params, "event_user_id"),
                        target_type=_str_param(params, "target_type"),
                        target_id=_str_param(params, "target_id"),
                        format=export_format,
                    )
                    content_type = "text/csv; charset=utf-8" if export_format_name == "csv" else "application/x-ndjson; charset=utf-8"
                    self._text(exported, content_type=content_type)
                finally:
                    store.close()
                return
            if parsed.path == "/audit-events":
                params = parse_qs(parsed.query)
                limit = _int_param(params, "limit", 100)
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit")
                    events = store.list_audit_events(
                        workspace_id,
                        user_id,
                        limit=limit,
                        since=_str_param(params, "since"),
                        until=_str_param(params, "until"),
                        action=_str_param(params, "action"),
                        event_user_id=_str_param(params, "event_user_id"),
                        target_type=_str_param(params, "target_type"),
                        target_id=_str_param(params, "target_id"),
                    )
                    self._json({"events": _redacted_audit_export_events(events)})
                finally:
                    store.close()
                return
            if parsed.path == "/audit-integrity":
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit")
                    self._json(store.verify_audit_integrity(workspace_id, user_id))
                finally:
                    store.close()
                return
            if parsed.path == "/query-runs/export":
                params = parse_qs(parsed.query)
                limit = _int_param(params, "limit", 500)
                export_format = _str_param(params, "format", "jsonl")
                export_format_name = (export_format or "jsonl").strip().casefold()
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
                    exported = store.export_query_runs(
                        workspace_id,
                        user_id,
                        limit=limit,
                        run_actor_user_id=_str_param(params, "actor_user_id"),
                        since=_str_param(params, "since"),
                        until=_str_param(params, "until"),
                        query=_str_param(params, "query"),
                        format=export_format,
                    )
                    content_type = "text/csv; charset=utf-8" if export_format_name == "csv" else "application/x-ndjson; charset=utf-8"
                    self._text(exported, content_type=content_type)
                finally:
                    store.close()
                return
            if parsed.path == "/query-runs":
                params = parse_qs(parsed.query)
                limit = _int_param(params, "limit", 50)
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
                    self._json(
                        {
                            "runs": store.list_query_runs(
                                workspace_id,
                                user_id,
                                limit=limit,
                                run_actor_user_id=_str_param(params, "actor_user_id"),
                                since=_str_param(params, "since"),
                                until=_str_param(params, "until"),
                                query=_str_param(params, "query"),
                            )
                        }
                    )
                finally:
                    store.close()
                return
            if parsed.path == "/query-source-sets":
                self._list_query_source_sets()
                return
            source_set_share_links_id = _query_source_set_share_links_path(parsed.path)
            if source_set_share_links_id:
                self._list_query_source_set_share_links(source_set_share_links_id)
                return
            query_run_id = _query_run_path(parsed.path)
            if query_run_id:
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
                    trace = store.get_query_trace(query_run_id, workspace_id=workspace_id, actor_user_id=user_id)
                    if trace is None:
                        self._json({"error": "query run not found"}, HTTPStatus.NOT_FOUND)
                        return
                    self._json({"trace": trace})
                finally:
                    store.close()
                return
            if parsed.path == "/audit-retention":
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit")
                    self._json(store.get_audit_retention_policy(workspace_id, user_id))
                finally:
                    store.close()
                return
            if parsed.path == "/audit-sink/check":
                self._check_audit_sink()
                return
            if parsed.path == "/audit-sink/status":
                self._get_audit_sink_status()
                return
            if parsed.path == "/audit-sink":
                self._get_audit_sink_config()
                return
            if parsed.path == "/query-retention":
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit")
                    self._json(store.get_query_retention_policy(workspace_id, user_id))
                finally:
                    store.close()
                return
            if parsed.path == "/deployment-check":
                self._deployment_check(parsed.query)
                return
            if parsed.path == "/provider-config/check":
                self._check_provider_config()
                return
            if parsed.path == "/provider-config":
                self._get_provider_config()
                return
            if parsed.path == "/api-token-policy":
                self._get_api_token_policy()
                return
            if parsed.path == "/workspace-quota-policy":
                self._get_workspace_quota_policy()
                return
            if parsed.path == "/api-tokens":
                self._list_api_tokens()
                return
            if parsed.path == "/folders":
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, _user_id = self._workspace_context(store, required_scope="read")
                    self._json({"folders": store.list_folders(workspace_id=workspace_id)})
                finally:
                    store.close()
                return
            if parsed.path == "/virtual-nodes":
                params = parse_qs(parsed.query)
                limit = max(1, min(_int_param(params, "limit", 10), 100))
                query_text = _str_param(params, "query")
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, _user_id = self._workspace_context(store, required_scope="read")
                    if query_text and query_text.strip():
                        self._json(store.plan_query_tree(query_text, limit=limit, workspace_id=workspace_id))
                    else:
                        self._json({"nodes": store.list_virtual_nodes(workspace_id=workspace_id)})
                finally:
                    store.close()
                return
            if parsed.path == "/documents":
                params = parse_qs(parsed.query)
                limit = _int_param(params, "limit", 50)
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="read")
                    self._json({"documents": store.list_documents(workspace_id=workspace_id, limit=limit, actor_user_id=user_id)})
                finally:
                    store.close()
                return
            document_share_links_id = _document_share_links_path(parsed.path)
            if document_share_links_id:
                self._list_document_share_links(document_share_links_id)
                return
            document_questions_id = _document_questions_path(parsed.path)
            if document_questions_id:
                params = parse_qs(parsed.query)
                limit = max(1, min(_int_param(params, "limit", 5), 8))
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="read")
                    self._json(
                        store.suggest_document_questions(
                            document_questions_id,
                            workspace_id=workspace_id,
                            actor_user_id=user_id,
                            limit=limit,
                        )
                    )
                finally:
                    store.close()
                return
            document_download_id = _document_download_path(parsed.path)
            if document_download_id:
                self._download_document(document_download_id)
                return
            document_access_id = _document_access_path(parsed.path)
            if document_access_id:
                self._get_document_access(document_access_id, parse_qs(parsed.query))
                return
            folder_access_id = _folder_access_path(parsed.path)
            if folder_access_id:
                self._get_folder_access(folder_access_id, parse_qs(parsed.query))
                return
            document_pages_id = _document_pages_path(parsed.path)
            if document_pages_id:
                params = parse_qs(parsed.query)
                limit = max(1, min(_int_param(params, "limit", 20), 100))
                offset = max(0, _int_param(params, "offset", 0))
                max_chars = max(200, min(_int_param(params, "max_chars", 4000), 20000))
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="read")
                    self._json(
                        store.list_document_pages(
                            document_pages_id,
                            workspace_id=workspace_id,
                            actor_user_id=user_id,
                            limit=limit,
                            offset=offset,
                            max_chars=max_chars,
                        )
                    )
                finally:
                    store.close()
                return
            document_versions_id = _document_versions_path(parsed.path)
            if document_versions_id:
                params = parse_qs(parsed.query)
                limit = _int_param(params, "limit", 100)
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="read")
                    self._json(
                        {
                            "versions": store.list_document_versions(
                                document_versions_id,
                                workspace_id=workspace_id,
                                actor_user_id=user_id,
                                limit=limit,
                            )
                        }
                    )
                finally:
                    store.close()
                return
            if parsed.path == "/workspace-export":
                self._workspace_export()
                return
            if parsed.path == "/workspace-invitations":
                params = parse_qs(parsed.query)
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
                    self._json(
                        {
                            "invitations": store.list_workspace_invitations(
                                workspace_id,
                                user_id,
                                status=_str_param(params, "status"),
                            )
                        }
                    )
                finally:
                    store.close()
                return
            if parsed.path == "/workspace-usage":
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
                    self._json({"usage": store.get_workspace_usage_summary(workspace_id, user_id)})
                finally:
                    store.close()
                return
            if parsed.path == "/managed-upload-orphans":
                self._get_managed_upload_orphans()
                return
            group_members_id = _workspace_group_members_path(parsed.path)
            if group_members_id:
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
                    self._json(
                        {
                            "members": store.list_workspace_group_members(
                                workspace_id,
                                user_id,
                                group_members_id,
                            )
                        }
                    )
                finally:
                    store.close()
                return
            if parsed.path == "/workspace-groups":
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
                    self._json({"groups": store.list_workspace_groups(workspace_id, user_id)})
                finally:
                    store.close()
                return
            if parsed.path == "/workspace-members":
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="audit")
                    self._json({"members": store.list_workspace_members(workspace_id, user_id)})
                finally:
                    store.close()
                return
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except RateLimitError as exc:
            self._rate_limit(exc)
        except PermissionError as exc:
            self._json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
        except ValueError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/upload-files":
                self._upload_files()
                return
            if parsed.path == "/upload-file":
                self._upload_file()
                return
            reindex_upload_id = _document_reindex_upload_path(parsed.path)
            if reindex_upload_id:
                self._reindex_document_upload(reindex_upload_id)
                return
            payload = self._read_json()
            if parsed.path == "/conversations":
                self._create_conversation(payload)
                return
            conversation_share_links_id = _conversation_share_links_path(parsed.path)
            if conversation_share_links_id:
                self._create_conversation_share_link(conversation_share_links_id, payload)
                return
            conversation_rename_id = _conversation_rename_path(parsed.path)
            if conversation_rename_id:
                self._rename_conversation(conversation_rename_id, payload)
                return
            conversation_archive_id = _conversation_archive_path(parsed.path)
            if conversation_archive_id:
                self._archive_conversation(conversation_archive_id, payload)
                return
            conversation_scope_id = _conversation_scope_path(parsed.path)
            if conversation_scope_id:
                self._update_conversation_scope(conversation_scope_id, payload)
                return
            conversation_id = _conversation_messages_path(parsed.path)
            if conversation_id:
                self._chat_message(conversation_id, payload)
                return
            if parsed.path == "/api-tokens":
                self._create_api_token(payload)
                return
            api_token_rotate_id = _api_token_rotate_path(parsed.path)
            if api_token_rotate_id:
                self._rotate_api_token(api_token_rotate_id)
                return
            if parsed.path == "/ingest-file":
                self._ingest_file(payload)
                return
            if parsed.path == "/folders":
                self._create_folder(payload)
                return
            if parsed.path == "/acl-bulk":
                self._apply_acl_bulk(payload)
                return
            document_share_links_id = _document_share_links_path(parsed.path)
            if document_share_links_id:
                self._create_document_share_link(document_share_links_id, payload)
                return
            folder_access_id = _folder_access_path(parsed.path)
            if folder_access_id:
                self._set_folder_access(folder_access_id, payload)
                return
            folder_move_id = _folder_move_path(parsed.path)
            if folder_move_id:
                self._move_folder(folder_move_id, payload)
                return
            if parsed.path == "/import-structure":
                self._import_structure(payload)
                return
            if parsed.path == "/workspace-import":
                self._workspace_import_restore(payload)
                return
            if parsed.path == "/workspace-import/preview":
                self._workspace_import_preview(payload)
                return
            if parsed.path == "/workspace-members":
                self._upsert_workspace_member(payload)
                return
            if parsed.path == "/workspace-invitations":
                self._create_workspace_invitation(payload)
                return
            if parsed.path == "/workspace-groups":
                self._create_workspace_group(payload)
                return
            group_members_id = _workspace_group_members_path(parsed.path)
            if group_members_id:
                self._add_workspace_group_member(group_members_id, payload)
                return
            if parsed.path == "/audit-retention":
                self._set_audit_retention(payload)
                return
            if parsed.path == "/audit-retention/purge":
                self._purge_audit_retention(payload)
                return
            if parsed.path == "/managed-upload-orphans/purge":
                self._purge_managed_upload_orphans(payload)
                return
            if parsed.path == "/audit-sink":
                self._set_audit_sink_config(payload)
                return
            if parsed.path == "/query-retention":
                self._set_query_retention(payload)
                return
            if parsed.path == "/query-retention/purge":
                self._purge_query_retention(payload)
                return
            if parsed.path == "/provider-config/probe":
                self._probe_provider_config()
                return
            if parsed.path == "/provider-config":
                self._set_provider_config(payload)
                return
            if parsed.path == "/api-token-policy":
                self._set_api_token_policy(payload)
                return
            if parsed.path == "/workspace-quota-policy":
                self._set_workspace_quota_policy(payload)
                return
            if parsed.path == "/query-source-sets":
                self._create_query_source_set(payload)
                return
            source_set_share_links_id = _query_source_set_share_links_path(parsed.path)
            if source_set_share_links_id:
                self._create_query_source_set_share_link(source_set_share_links_id, payload)
                return
            if parsed.path == "/chat/completions":
                self._chat_completion(payload)
                return
            if parsed.path == "/query":
                self._query(payload)
                return
            document_rename_id = _document_rename_path(parsed.path)
            if document_rename_id:
                self._rename_document(document_rename_id, payload)
                return
            document_move_id = _document_move_path(parsed.path)
            if document_move_id:
                self._move_document(document_move_id, payload)
                return
            document_access_id = _document_access_path(parsed.path)
            if document_access_id:
                self._set_document_access(document_access_id, payload)
                return
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except RateLimitError as exc:
            self._rate_limit(exc)
        except PermissionError as exc:
            self._json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
        except LLMProviderError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        except (ValueError, FileNotFoundError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_PUT(self) -> None:
        try:
            parsed = urlparse(self.path)
            query_source_set_id = _query_source_set_path(parsed.path)
            if query_source_set_id:
                self._update_query_source_set(query_source_set_id, self._read_json())
                return
            folder_id = _folder_path(parsed.path)
            if folder_id:
                self._rename_folder(folder_id, self._read_json())
                return
            group_id = _workspace_group_path(parsed.path)
            if group_id:
                self._rename_workspace_group(group_id, self._read_json())
                return
            doc_id = _document_path(parsed.path)
            if doc_id:
                self._reindex_document(doc_id, self._read_json())
                return
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except RateLimitError as exc:
            self._rate_limit(exc)
        except PermissionError as exc:
            self._json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
        except (ValueError, FileNotFoundError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        try:
            parsed = urlparse(self.path)
            api_token_id = _api_token_path(parsed.path)
            if api_token_id:
                self._revoke_api_token(api_token_id)
                return
            member_user_id = _workspace_member_path(parsed.path)
            if member_user_id:
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="write")
                    removed = store.remove_workspace_member(workspace_id, member_user_id, user_id)
                    self._json({"removed": removed})
                finally:
                    store.close()
                return
            invitation_id = _workspace_invitation_path(parsed.path)
            if invitation_id:
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(
                        store,
                        required_scope=("audit", "write"),
                        require_api_token=True,
                    )
                    revoked = store.revoke_workspace_invitation(workspace_id, user_id, invitation_id)
                    self._json({"revoked": revoked})
                finally:
                    store.close()
                return
            group_member = _workspace_group_member_path(parsed.path)
            if group_member:
                group_id, group_user_id = group_member
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(
                        store,
                        required_scope=("audit", "write"),
                        require_api_token=True,
                    )
                    removed = store.remove_workspace_group_member(workspace_id, user_id, group_id, group_user_id)
                    self._json({"removed": removed})
                finally:
                    store.close()
                return
            group_id = _workspace_group_path(parsed.path)
            if group_id:
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(
                        store,
                        required_scope=("audit", "write"),
                        require_api_token=True,
                    )
                    deleted = store.delete_workspace_group(workspace_id, user_id, group_id)
                    self._json({"deleted": deleted})
                finally:
                    store.close()
                return
            folder_id = _folder_path(parsed.path)
            if folder_id:
                self._delete_folder(folder_id)
                return
            document_share_link_id = _document_share_link_path(parsed.path)
            if document_share_link_id:
                self._revoke_document_share_link(document_share_link_id)
                return
            query_run_id = _query_run_path(parsed.path)
            if query_run_id:
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(
                        store,
                        required_scope=("audit", "write"),
                        require_api_token=True,
                    )
                    deleted = store.delete_query_run(query_run_id, workspace_id=workspace_id, actor_user_id=user_id)
                    self._json({"deleted": deleted})
                finally:
                    store.close()
                return
            query_source_set_id = _query_source_set_path(parsed.path)
            if query_source_set_id:
                self._delete_query_source_set(query_source_set_id)
                return
            conversation_id = _conversation_path(parsed.path)
            if conversation_id:
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="write")
                    deleted = store.delete_conversation(
                        conversation_id,
                        user_id,
                        expected_workspace_id=workspace_id,
                    )
                    self._json({"deleted": deleted})
                finally:
                    store.close()
                return
            conversation_share_link_id = _conversation_share_link_path(parsed.path)
            if conversation_share_link_id:
                self._revoke_conversation_share_link(conversation_share_link_id)
                return
            source_set_share_link_id = _query_source_set_share_link_path(parsed.path)
            if source_set_share_link_id:
                self._revoke_query_source_set_share_link(source_set_share_link_id)
                return
            doc_id = _document_path(parsed.path)
            if doc_id:
                store = EnterpriseStore(self.server.root)
                try:
                    workspace_id, user_id = self._workspace_context(store, required_scope="write")
                    deleted = store.delete_document(doc_id, workspace_id=workspace_id, actor_user_id=user_id)
                    self._json({"deleted": deleted})
                finally:
                    store.close()
                return
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except PermissionError as exc:
            self._json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
        except ValueError as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _create_conversation(self, payload: dict[str, Any]) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            self._json(
                store.create_conversation(
                    workspace_id,
                    user_id,
                    title=_optional_str(payload.get("title"), "title"),
                    source_set_id=_optional_str(
                        payload.get("source_set_id", payload.get("sourceSetId")),
                        "source_set_id",
                    ),
                    folder_id=_optional_str(
                        payload.get("folder_id", payload.get("folderId")),
                        "folder_id",
                    ),
                ),
                HTTPStatus.CREATED,
            )
        finally:
            store.close()

    def _chat_message(self, conversation_id: str, payload: dict[str, Any]) -> None:
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            self._json(
                store.chat_message(
                    conversation_id,
                    user_id,
                    message,
                    doc_ids=_list_or_none(payload.get("doc_ids")),
                    expert_hints=_list_or_none(payload.get("expert_hints")),
                    limit=int(payload.get("limit", 8)),
                    expected_workspace_id=workspace_id,
                )
            )
        finally:
            store.close()

    def _archive_conversation(self, conversation_id: str, payload: dict[str, Any]) -> None:
        archived = _bool_body_value(payload.get("archived", True), "archived")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            self._json(
                {
                    "conversation": store.archive_conversation(
                        conversation_id,
                        user_id,
                        archived=archived,
                        expected_workspace_id=workspace_id,
                    )
                }
            )
        finally:
            store.close()

    def _rename_conversation(self, conversation_id: str, payload: dict[str, Any]) -> None:
        title = payload.get("title")
        if not isinstance(title, str):
            raise ValueError("title is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            self._json(
                {
                    "conversation": store.rename_conversation(
                        conversation_id,
                        user_id,
                        title,
                        expected_workspace_id=workspace_id,
                    )
                }
            )
        finally:
            store.close()

    def _update_conversation_scope(self, conversation_id: str, payload: dict[str, Any]) -> None:
        clear_scope = payload.get("clear", payload.get("clear_scope", payload.get("clearScope", False)))
        if not isinstance(clear_scope, bool):
            raise ValueError("clear_scope must be a boolean")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            self._json(
                {
                    "conversation": store.update_conversation_scope(
                        conversation_id,
                        user_id,
                        source_set_id=_optional_str(
                            payload.get("source_set_id", payload.get("sourceSetId")),
                            "source_set_id",
                        ),
                        folder_id=_optional_str(
                            payload.get("folder_id", payload.get("folderId")),
                            "folder_id",
                        ),
                        clear_scope=clear_scope,
                        expected_workspace_id=workspace_id,
                    )
                }
            )
        finally:
            store.close()

    def _list_conversation_share_links(self, conversation_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            self._json(
                {
                    "share_links": store.list_conversation_share_links(
                        conversation_id,
                        user_id,
                        expected_workspace_id=workspace_id,
                    )
                }
            )
        finally:
            store.close()

    def _create_conversation_share_link(self, conversation_id: str, payload: dict[str, Any]) -> None:
        if payload.get("expires_at") is not None and payload.get("expires_in_days") is not None:
            raise ValueError("choose expires_at or expires_in_days")
        expires_at = _optional_str(payload.get("expires_at"), "expires_at")
        if payload.get("expires_in_days") is not None:
            expires_at = expires_at_from_days(_optional_positive_int(payload.get("expires_in_days"), "expires_in_days"))
        redact_content = (
            _bool_body_value(payload.get("redact_content"), "redact_content")
            if "redact_content" in payload
            else False
        )
        max_views = _optional_positive_int(payload.get("max_views"), "max_views") if "max_views" in payload else None
        password = _optional_str(payload.get("password"), "password") if "password" in payload else None
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            self._json(
                {
                    "share_link": store.create_conversation_share_link(
                        conversation_id,
                        user_id,
                        expected_workspace_id=workspace_id,
                        expires_at=expires_at,
                        redact_content=redact_content,
                        max_views=max_views,
                        password=password,
                    )
                },
                HTTPStatus.CREATED,
            )
        finally:
            store.close()

    def _revoke_conversation_share_link(self, share_link_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            revoked = store.revoke_conversation_share_link(
                share_link_id,
                user_id,
                expected_workspace_id=workspace_id,
            )
            self._json({"revoked": revoked})
        finally:
            store.close()

    def _public_conversation_share(self, token: str, query: str) -> None:
        params = parse_qs(query)
        limit = max(1, min(_int_param(params, "limit", 100), 500))
        password = _share_password_value(params, self.headers)
        store = EnterpriseStore(self.server.root)
        try:
            shared = store.resolve_conversation_share_link(token, password=password, limit=limit)
            if shared is None:
                self._json({"error": "share link not found"}, HTTPStatus.NOT_FOUND)
                return
            wants_html = _share_response_wants_html(self.headers.get("Accept", ""), _str_param(params, "format"))
            recorded = store.record_conversation_share_link_view(
                token,
                password=password,
                response_format="html" if wants_html else "json",
                limit=limit,
            )
            if not recorded:
                self._json({"error": "share link not found"}, HTTPStatus.NOT_FOUND)
                return
            if wants_html:
                self._html(_render_public_conversation_share(shared))
                return
            self._json(shared)
        finally:
            store.close()

    def _list_api_tokens(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            verified = self._api_token_context(store, required_scope="write")
            self._json({"tokens": store.list_api_tokens(verified["workspace_id"], verified["user_id"])})
        finally:
            store.close()

    def _get_api_token_policy(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            self._json(store.get_api_token_policy(workspace_id, user_id))
        finally:
            store.close()

    def _set_api_token_policy(self, payload: dict[str, Any]) -> None:
        updates: dict[str, int | None] = {}
        default_clear = _bool_body_value(payload.get("clear_default_expiration", False), "clear_default_expiration")
        rotation_clear = _bool_body_value(payload.get("clear_rotation_due", False), "clear_rotation_due")
        if default_clear and payload.get("default_expires_in_days") is not None:
            raise ValueError("choose default_expires_in_days or clear_default_expiration")
        if rotation_clear and payload.get("rotation_due_in_days") is not None:
            raise ValueError("choose rotation_due_in_days or clear_rotation_due")
        if default_clear or "default_expires_in_days" in payload:
            updates["default_expires_in_days"] = None if default_clear else _optional_positive_int(
                payload.get("default_expires_in_days"), "default_expires_in_days"
            )
        if rotation_clear or "rotation_due_in_days" in payload:
            updates["rotation_due_in_days"] = None if rotation_clear else _optional_positive_int(
                payload.get("rotation_due_in_days"), "rotation_due_in_days"
            )
        if not updates:
            raise ValueError("token policy update is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            self._json(store.set_api_token_policy(workspace_id, user_id, **updates))
        finally:
            store.close()

    def _get_workspace_quota_policy(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            self._json(store.get_workspace_quota_policy(workspace_id, user_id))
        finally:
            store.close()

    def _set_workspace_quota_policy(self, payload: dict[str, Any]) -> None:
        updates: dict[str, int | None] = {}
        for name in ("max_documents", "max_pages", "max_members"):
            if name in payload:
                updates[name] = _optional_positive_int(payload.get(name), name)
        if not updates:
            raise ValueError("workspace quota policy update is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            self._json(store.set_workspace_quota_policy(workspace_id, user_id, **updates))
        finally:
            store.close()

    def _create_api_token(self, payload: dict[str, Any]) -> None:
        if payload.get("expires_at") is not None:
            raise ValueError("expires_at is not supported; use expires_in_days")
        store = EnterpriseStore(self.server.root)
        try:
            verified = self._api_token_context(store, required_scope="write")
            expires_in_days = _optional_positive_int(payload.get("expires_in_days"), "expires_in_days")
            scopes = _token_scopes_from_payload(payload.get("scopes"), verified["scopes"])
            token = store.create_api_token(
                verified["workspace_id"],
                verified["user_id"],
                name=_optional_str(payload.get("name"), "name") or "default",
                expires_at=expires_at_from_days(expires_in_days),
                scopes=scopes,
            )
            self._json({"token": token}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _revoke_api_token(self, token_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            verified = self._api_token_context(store, required_scope="write")
            revoked = store.revoke_api_token(verified["workspace_id"], verified["user_id"], token_id)
            self._json({"revoked": revoked})
        finally:
            store.close()

    def _rotate_api_token(self, token_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            verified = self._api_token_context(store, required_scope="write")
            target = _find_token_metadata(
                store.list_api_tokens(verified["workspace_id"], verified["user_id"]),
                token_id,
            )
            if target is None:
                self._json({"error": "token not found"}, HTTPStatus.NOT_FOUND)
                return
            _require_scopes_within_token(target["scopes"], verified["scopes"])
            rotated = store.rotate_api_token(verified["workspace_id"], verified["user_id"], token_id)
            if rotated is None:
                self._json({"error": "token not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json({"token": rotated})
        finally:
            store.close()

    def _create_folder(self, payload: dict[str, Any]) -> None:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            folder_id = store.create_folder(
                name,
                parent_id=_optional_str(payload.get("parent_id"), "parent_id"),
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            self._json({"folder_id": folder_id}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _rename_folder(self, folder_id: str, payload: dict[str, Any]) -> None:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            folder = store.rename_folder(
                folder_id,
                name,
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            if folder is None:
                self._json({"error": "folder not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json({"folder": folder})
        finally:
            store.close()

    def _delete_folder(self, folder_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            deleted = store.delete_folder(folder_id, workspace_id=workspace_id, actor_user_id=user_id)
            self._json({"deleted": deleted})
        finally:
            store.close()

    def _move_folder(self, folder_id: str, payload: dict[str, Any]) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            folder = store.move_folder(
                folder_id,
                parent_id=_optional_str(payload.get("parent_id"), "parent_id"),
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            if folder is None:
                self._json({"error": "folder not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json({"folder": folder})
        finally:
            store.close()

    def _get_folder_access(self, folder_id: str, params: dict[str, list[str]] | None = None) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            access = store.list_folder_access(folder_id, workspace_id=workspace_id, actor_user_id=user_id)
            if access is None:
                self._json({"error": "folder not found"}, HTTPStatus.NOT_FOUND)
                return
            effective_user_id = _str_param(params or {}, "effective_user_id")
            if effective_user_id:
                access["effective_access"] = store.explain_folder_access(
                    folder_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    target_user_id=effective_user_id,
                )
            self._json({"access": access})
        finally:
            store.close()

    def _set_folder_access(self, folder_id: str, payload: dict[str, Any]) -> None:
        actions = [
            key
            for key in ("grant_user_id", "revoke_user_id", "grant_group_id", "revoke_group_id")
            if key in payload and payload[key] is not None
        ]
        if len(actions) != 1:
            raise ValueError("choose exactly one folder access update")
        grant_role = payload.get("grant_role", "read")
        if "grant_role" in payload and not isinstance(grant_role, str):
            raise ValueError("grant_role must be a string")
        if "grant_role" in payload and actions[0] not in {"grant_user_id", "grant_group_id"}:
            raise ValueError("grant_role only applies to grant updates")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            action = actions[0]
            if action == "grant_user_id":
                grant_user_id = payload.get("grant_user_id")
                if not isinstance(grant_user_id, str):
                    raise ValueError("grant_user_id must be a string")
                access = store.grant_folder_access(
                    folder_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    user_id=grant_user_id,
                    role=grant_role,
                )
                if access is None:
                    self._json({"error": "folder not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._json({"access": access})
                return
            if action == "grant_group_id":
                grant_group_id = payload.get("grant_group_id")
                if not isinstance(grant_group_id, str):
                    raise ValueError("grant_group_id must be a string")
                access = store.grant_folder_group_access(
                    folder_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    group_id=grant_group_id,
                    role=grant_role,
                )
                if access is None:
                    self._json({"error": "folder not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._json({"access": access})
                return
            if action == "revoke_group_id":
                revoke_group_id = payload.get("revoke_group_id")
                if not isinstance(revoke_group_id, str):
                    raise ValueError("revoke_group_id must be a string")
                access = store.list_folder_access(folder_id, workspace_id=workspace_id, actor_user_id=user_id)
                if access is None:
                    self._json({"error": "folder not found"}, HTTPStatus.NOT_FOUND)
                    return
                revoked = store.revoke_folder_group_access(
                    folder_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    group_id=revoke_group_id,
                )
                access = store.list_folder_access(folder_id, workspace_id=workspace_id, actor_user_id=user_id)
                self._json({"revoked": revoked, "access": access})
                return
            revoke_user_id = payload.get("revoke_user_id")
            if not isinstance(revoke_user_id, str):
                raise ValueError("revoke_user_id must be a string")
            access = store.list_folder_access(folder_id, workspace_id=workspace_id, actor_user_id=user_id)
            if access is None:
                self._json({"error": "folder not found"}, HTTPStatus.NOT_FOUND)
                return
            revoked = store.revoke_folder_access(
                folder_id,
                workspace_id=workspace_id,
                actor_user_id=user_id,
                user_id=revoke_user_id,
            )
            access = store.list_folder_access(folder_id, workspace_id=workspace_id, actor_user_id=user_id)
            self._json({"revoked": revoked, "access": access})
        finally:
            store.close()

    def _apply_acl_bulk(self, payload: dict[str, Any]) -> None:
        policy = payload.get("policy")
        if policy is None:
            policy = {
                "document_grants": payload.get("document_grants", []),
                "folder_grants": payload.get("folder_grants", []),
                "document_revokes": payload.get("document_revokes", []),
                "folder_revokes": payload.get("folder_revokes", []),
                "document_reconciles": payload.get("document_reconciles", []),
                "folder_reconciles": payload.get("folder_reconciles", []),
            }
        if not isinstance(policy, dict):
            raise ValueError("policy must be an object")
        dry_run = payload.get("dry_run", True)
        if not isinstance(dry_run, bool):
            raise ValueError("dry_run must be boolean")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            self._json(store.apply_acl_bulk(workspace_id, user_id, policy, dry_run=dry_run))
        finally:
            store.close()

    def _import_structure(self, payload: dict[str, Any]) -> None:
        path = payload.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("path is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            doc_id = store.import_pageindex_structure(
                path,
                doc_id=payload.get("doc_id"),
                folder_id=payload.get("folder_id"),
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            self._json({"doc_id": doc_id}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _ingest_file(self, payload: dict[str, Any]) -> None:
        path = payload.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("path is required")
        if payload.get("doc_id") is not None:
            raise ValueError("doc_id is not supported")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            doc_id = store.ingest_file(
                path,
                folder_id=_optional_str(payload.get("folder_id"), "folder_id"),
                name=_optional_str(payload.get("name"), "name"),
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            self._json({"doc_id": doc_id}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _upload_file(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            upload = self._read_multipart_file()
            stored_path, filename = self._store_upload_file(workspace_id, upload)
            try:
                doc_id = store.ingest_file(
                    stored_path,
                    folder_id=_optional_str(upload.get("folder_id"), "folder_id"),
                    name=upload.get("name") or filename,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    audit_action="document.upload",
                )
            except Exception:
                stored_path.unlink(missing_ok=True)
                raise
            self._json({"doc_id": doc_id, "stored_path": str(stored_path)}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _upload_files(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            uploads = self._read_multipart_files()
            documents: list[dict[str, Any]] = []
            errors: list[dict[str, str]] = []
            for upload in uploads:
                stored_path: Path | None = None
                filename = _safe_upload_filename(upload["filename"])
                try:
                    stored_path, filename = self._store_upload_file(workspace_id, upload)
                    doc_id = store.ingest_file(
                        stored_path,
                        folder_id=_optional_str(upload.get("folder_id"), "folder_id"),
                        name=upload.get("name") or filename,
                        workspace_id=workspace_id,
                        actor_user_id=user_id,
                        audit_action="document.upload",
                    )
                except Exception as exc:
                    if stored_path:
                        stored_path.unlink(missing_ok=True)
                    errors.append({"filename": filename, "error": str(exc)})
                else:
                    documents.append({"filename": filename, "doc_id": doc_id, "stored_path": str(stored_path)})
            status = HTTPStatus.CREATED if documents else HTTPStatus.BAD_REQUEST
            self._json({"documents": documents, "errors": errors}, status)
        finally:
            store.close()

    def _store_upload_file(self, workspace_id: str, upload: dict[str, Any]) -> tuple[Path, str]:
        uploads_root = Path(self.server.root).expanduser().resolve() / "uploads"
        upload_dir = (uploads_root / _safe_path_segment(workspace_id)).resolve()
        if not _is_relative_to(upload_dir, uploads_root.resolve()):
            raise ValueError("workspace upload path is invalid")
        upload_dir.mkdir(parents=True, exist_ok=True)
        filename = _safe_upload_filename(upload["filename"])
        stored_path = upload_dir / f"{uuid.uuid4().hex}_{filename}"
        stored_path.write_bytes(upload["content"])
        return stored_path, filename

    def _reindex_document(self, doc_id: str, payload: dict[str, Any]) -> None:
        path = payload.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("path is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            document = store.reindex_document_file(
                doc_id,
                path,
                name=_optional_str(payload.get("name"), "name"),
                folder_id=_optional_str(payload.get("folder_id"), "folder_id"),
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            if document is None:
                self._json({"updated": False})
                return
            self._json({"updated": True, "document": document})
        finally:
            store.close()

    def _rename_document(self, doc_id: str, payload: dict[str, Any]) -> None:
        name = payload.get("name")
        if not isinstance(name, str):
            raise ValueError("Document name is required.")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            document = store.rename_document(
                doc_id,
                name,
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            if document is None:
                self._json({"updated": False})
                return
            self._json({"updated": True, "document": document})
        finally:
            store.close()

    def _move_document(self, doc_id: str, payload: dict[str, Any]) -> None:
        folder_id = _optional_str(payload.get("folder_id"), "folder_id")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            document = store.move_document(
                doc_id,
                folder_id,
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            if document is None:
                self._json({"updated": False})
                return
            self._json({"updated": True, "document": document})
        finally:
            store.close()

    def _reindex_document_upload(self, doc_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            upload = self._read_multipart_file()
            stored_path, filename = self._store_upload_file(workspace_id, upload)
            try:
                document = store.reindex_document_file(
                    doc_id,
                    stored_path,
                    name=upload.get("name") or filename,
                    folder_id=_optional_str(upload.get("folder_id"), "folder_id"),
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                )
            except Exception:
                stored_path.unlink(missing_ok=True)
                raise
            if document is None:
                stored_path.unlink(missing_ok=True)
                self._json({"updated": False})
                return
            self._json({"updated": True, "document": document, "stored_path": str(stored_path)})
        finally:
            store.close()

    def _download_document(self, doc_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="read")
            try:
                download = store.get_managed_upload_document_file(
                    doc_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                )
            except FileNotFoundError:
                self._json({"error": "document file not found"}, HTTPStatus.NOT_FOUND)
                return
            if download is None:
                self._json({"error": "document not found"}, HTTPStatus.NOT_FOUND)
                return
            path = download["path"]
            document = download["document"]
            filename = _safe_download_filename(str(document.get("name") or path.name), path.name)
            self._bytes(
                path.read_bytes(),
                content_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        finally:
            store.close()

    def _list_document_share_links(self, doc_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            self._json(
                {
                    "share_links": store.list_document_share_links(
                        doc_id,
                        workspace_id=workspace_id,
                        actor_user_id=user_id,
                    )
                }
            )
        finally:
            store.close()

    def _create_document_share_link(self, doc_id: str, payload: dict[str, Any]) -> None:
        if payload.get("expires_at") is not None and payload.get("expires_in_days") is not None:
            raise ValueError("choose expires_at or expires_in_days")
        expires_at = _optional_str(payload.get("expires_at"), "expires_at")
        if payload.get("expires_in_days") is not None:
            expires_at = expires_at_from_days(_optional_positive_int(payload.get("expires_in_days"), "expires_in_days"))
        redact_content = (
            _bool_body_value(payload.get("redact_content"), "redact_content")
            if "redact_content" in payload
            else False
        )
        max_views = _optional_positive_int(payload.get("max_views"), "max_views") if "max_views" in payload else None
        password = _optional_str(payload.get("password"), "password") if "password" in payload else None
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            share_link = store.create_document_share_link(
                doc_id,
                workspace_id=workspace_id,
                actor_user_id=user_id,
                expires_at=expires_at,
                redact_content=redact_content,
                max_views=max_views,
                password=password,
            )
            if share_link is None:
                self._json({"error": "document not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json({"share_link": share_link}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _revoke_document_share_link(self, share_link_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="write")
            revoked = store.revoke_document_share_link(
                share_link_id,
                workspace_id=workspace_id,
                actor_user_id=user_id,
            )
            self._json({"revoked": revoked})
        finally:
            store.close()

    def _public_document_share(self, token: str, query: str) -> None:
        params = parse_qs(query)
        limit = max(1, min(_int_param(params, "limit", 20), 100))
        offset = max(0, _int_param(params, "offset", 0))
        max_chars = max(200, min(_int_param(params, "max_chars", 4000), 20000))
        password = _share_password_value(params, self.headers)
        store = EnterpriseStore(self.server.root)
        try:
            shared = store.resolve_document_share_link(
                token,
                limit=limit,
                offset=offset,
                max_chars=max_chars,
                password=password,
            )
            if shared is None:
                self._json({"error": "share link not found"}, HTTPStatus.NOT_FOUND)
                return
            wants_html = _share_response_wants_html(self.headers.get("Accept", ""), _str_param(params, "format"))
            recorded = store.record_document_share_link_view(
                token,
                password=password,
                response_format="html" if wants_html else "json",
                limit=limit,
                offset=offset,
                max_chars=max_chars,
            )
            if not recorded:
                self._json({"error": "share link not found"}, HTTPStatus.NOT_FOUND)
                return
            if wants_html:
                self._html(_render_public_document_share(shared))
                return
            self._json(shared)
        finally:
            store.close()

    def _create_workspace_invitation(self, payload: dict[str, Any]) -> None:
        email = payload.get("email")
        if not isinstance(email, str) or not email.strip():
            raise ValueError("email is required")
        if payload.get("expires_at") is not None and payload.get("expires_in_days") is not None:
            raise ValueError("choose expires_at or expires_in_days")
        expires_at = _optional_str(payload.get("expires_at"), "expires_at")
        if payload.get("expires_in_days") is not None:
            expires_at = expires_at_from_days(_optional_positive_int(payload.get("expires_in_days"), "expires_in_days"))
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            invitation = store.create_workspace_invitation(
                workspace_id,
                user_id,
                email,
                role=_optional_str(payload.get("role"), "role") or "member",
                expires_at=expires_at,
            )
            self._json({"invitation": invitation}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _create_workspace_group(self, payload: dict[str, Any]) -> None:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            group = store.create_workspace_group(workspace_id, user_id, name)
            self._json({"group": group}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _add_workspace_group_member(self, group_id: str, payload: dict[str, Any]) -> None:
        target_user_id = payload.get("user_id")
        if not isinstance(target_user_id, str) or not target_user_id.strip():
            raise ValueError("user_id is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            group = store.add_workspace_group_member(workspace_id, user_id, group_id, target_user_id)
            self._json({"group": group})
        finally:
            store.close()

    def _rename_workspace_group(self, group_id: str, payload: dict[str, Any]) -> None:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            group = store.rename_workspace_group(workspace_id, user_id, group_id, name)
            self._json({"group": group})
        finally:
            store.close()

    def _workspace_export(self) -> None:
        store = EnterpriseStore(self.server.root)
        output: Path | None = None
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            root = Path(self.server.root).expanduser().resolve()
            export_dir = (root / "exports").resolve()
            if not _is_relative_to(export_dir, root):
                raise ValueError("workspace export path is invalid")
            export_dir.mkdir(parents=True, exist_ok=True)
            output = export_dir / f"workspace-export-{uuid.uuid4().hex}.zip"
            store.export_workspace_bundle(workspace_id, user_id, output)
            body = output.read_bytes()
            filename = f"pageindex-{_safe_path_segment(workspace_id)}-workspace-export.zip"
            self._bytes(
                body,
                content_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        finally:
            if output is not None:
                output.unlink(missing_ok=True)
            store.close()

    def _workspace_import_preview(self, payload: dict[str, Any]) -> None:
        path = payload.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            store.require_workspace_role(workspace_id, user_id, WORKSPACE_ADMIN_ROLES)
            self._json(store.validate_workspace_import_bundle(path))
        finally:
            store.close()

    def _workspace_import_restore(self, payload: dict[str, Any]) -> None:
        path = payload.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path is required")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            store.require_workspace_role(workspace_id, user_id, {"owner"})
            report = store.import_workspace_bundle(path)
            store.record_audit_event(
                workspace_id,
                user_id,
                "workspace.import",
                target_type="workspace",
                target_id=report["workspace_id"],
                details={
                    "artifact": report["artifact"],
                    "workspace_id": report["workspace_id"],
                    "inserted": report["inserted"],
                },
            )
            self._json(report, HTTPStatus.CREATED)
        finally:
            store.close()

    def _get_document_access(self, doc_id: str, params: dict[str, list[str]] | None = None) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            access = store.list_document_access(doc_id, workspace_id=workspace_id, actor_user_id=user_id)
            if access is None:
                self._json({"error": "document not found"}, HTTPStatus.NOT_FOUND)
                return
            effective_user_id = _str_param(params or {}, "effective_user_id")
            if effective_user_id:
                access["effective_access"] = store.explain_document_access(
                    doc_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    target_user_id=effective_user_id,
                )
            self._json({"access": access})
        finally:
            store.close()

    def _set_document_access(self, doc_id: str, payload: dict[str, Any]) -> None:
        actions = [
            key
            for key in ("access_mode", "grant_user_id", "revoke_user_id", "grant_group_id", "revoke_group_id")
            if key in payload and payload[key] is not None
        ]
        if len(actions) != 1:
            raise ValueError("choose exactly one document access update")
        grant_role = payload.get("grant_role", "read")
        if "grant_role" in payload and not isinstance(grant_role, str):
            raise ValueError("grant_role must be a string")
        if "grant_role" in payload and actions[0] not in {"grant_user_id", "grant_group_id"}:
            raise ValueError("grant_role only applies to grant updates")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=("audit", "write"),
                require_api_token=True,
            )
            action = actions[0]
            if action == "access_mode":
                access_mode = payload.get("access_mode")
                if not isinstance(access_mode, str):
                    raise ValueError("access_mode must be a string")
                access = store.set_document_access_mode(
                    doc_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    access_mode=access_mode,
                )
                if access is None:
                    self._json({"error": "document not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._json({"access": access})
                return
            if action == "grant_user_id":
                grant_user_id = payload.get("grant_user_id")
                if not isinstance(grant_user_id, str):
                    raise ValueError("grant_user_id must be a string")
                access = store.grant_document_access(
                    doc_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    user_id=grant_user_id,
                    role=grant_role,
                )
                if access is None:
                    self._json({"error": "document not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._json({"access": access})
                return
            if action == "grant_group_id":
                grant_group_id = payload.get("grant_group_id")
                if not isinstance(grant_group_id, str):
                    raise ValueError("grant_group_id must be a string")
                access = store.grant_document_group_access(
                    doc_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    group_id=grant_group_id,
                    role=grant_role,
                )
                if access is None:
                    self._json({"error": "document not found"}, HTTPStatus.NOT_FOUND)
                    return
                self._json({"access": access})
                return
            if action == "revoke_group_id":
                revoke_group_id = payload.get("revoke_group_id")
                if not isinstance(revoke_group_id, str):
                    raise ValueError("revoke_group_id must be a string")
                access = store.list_document_access(doc_id, workspace_id=workspace_id, actor_user_id=user_id)
                if access is None:
                    self._json({"error": "document not found"}, HTTPStatus.NOT_FOUND)
                    return
                revoked = store.revoke_document_group_access(
                    doc_id,
                    workspace_id=workspace_id,
                    actor_user_id=user_id,
                    group_id=revoke_group_id,
                )
                access = store.list_document_access(doc_id, workspace_id=workspace_id, actor_user_id=user_id)
                self._json({"revoked": revoked, "access": access})
                return
            revoke_user_id = payload.get("revoke_user_id")
            if not isinstance(revoke_user_id, str):
                raise ValueError("revoke_user_id must be a string")
            access = store.list_document_access(doc_id, workspace_id=workspace_id, actor_user_id=user_id)
            if access is None:
                self._json({"error": "document not found"}, HTTPStatus.NOT_FOUND)
                return
            revoked = store.revoke_document_access(
                doc_id,
                workspace_id=workspace_id,
                actor_user_id=user_id,
                user_id=revoke_user_id,
            )
            access = store.list_document_access(doc_id, workspace_id=workspace_id, actor_user_id=user_id)
            self._json({"revoked": revoked, "access": access})
        finally:
            store.close()

    def _upsert_workspace_member(self, payload: dict[str, Any]) -> None:
        target_user_id = payload.get("user_id")
        if not isinstance(target_user_id, str) or not target_user_id.strip():
            raise ValueError("user_id is required")
        role = payload.get("role", "member")
        if not isinstance(role, str):
            raise ValueError("role must be a string")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, actor_user_id = self._workspace_context(store, required_scope="write")
            store.add_workspace_member(workspace_id, target_user_id, role, actor_user_id=actor_user_id)
            self._json(
                {
                    "member": {
                        "workspace_id": workspace_id,
                        "user_id": target_user_id.strip(),
                        "role": role.strip() or "member",
                    }
                }
            )
        finally:
            store.close()

    def _set_audit_retention(self, payload: dict[str, Any]) -> None:
        clear = payload.get("clear", False)
        if not isinstance(clear, bool):
            raise ValueError("clear must be a boolean")
        has_retention_days = "retention_days" in payload and payload.get("retention_days") is not None
        has_legal_hold = "legal_hold" in payload
        legal_hold = payload.get("legal_hold")
        if has_legal_hold and not isinstance(legal_hold, bool):
            raise ValueError("legal_hold must be a boolean")
        has_legal_hold_reason = "legal_hold_reason" in payload
        legal_hold_reason = payload.get("legal_hold_reason")
        if has_legal_hold_reason and legal_hold_reason is not None and not isinstance(legal_hold_reason, str):
            raise ValueError("legal_hold_reason must be a string")
        if clear and has_retention_days:
            raise ValueError("choose retention_days or clear")
        if not clear and not has_retention_days and not has_legal_hold and not has_legal_hold_reason:
            raise ValueError("retention_days, legal_hold, or legal_hold_reason is required")
        retention_days = None
        if has_retention_days:
            retention_days = payload["retention_days"]
            if isinstance(retention_days, bool) or not isinstance(retention_days, int):
                raise ValueError("retention_days must be a positive integer")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope=("audit", "write"))
            self._json(
                store.set_audit_retention_policy(
                    workspace_id,
                    user_id,
                    retention_days=None if clear else (retention_days if has_retention_days else _UNSET),
                    legal_hold=legal_hold if has_legal_hold else _UNSET,
                    legal_hold_reason=legal_hold_reason if has_legal_hold_reason else _UNSET,
                )
            )
        finally:
            store.close()

    def _set_query_retention(self, payload: dict[str, Any]) -> None:
        clear = payload.get("clear", False)
        if not isinstance(clear, bool):
            raise ValueError("clear must be a boolean")
        has_retention_days = "retention_days" in payload and payload.get("retention_days") is not None
        has_legal_hold = "legal_hold" in payload
        legal_hold = payload.get("legal_hold")
        if has_legal_hold and not isinstance(legal_hold, bool):
            raise ValueError("legal_hold must be a boolean")
        has_legal_hold_reason = "legal_hold_reason" in payload
        legal_hold_reason = payload.get("legal_hold_reason")
        if has_legal_hold_reason and legal_hold_reason is not None and not isinstance(legal_hold_reason, str):
            raise ValueError("legal_hold_reason must be a string")
        if clear and has_retention_days:
            raise ValueError("choose retention_days or clear")
        if not clear and not has_retention_days and not has_legal_hold and not has_legal_hold_reason:
            raise ValueError("retention_days, legal_hold, or legal_hold_reason is required")
        retention_days = None
        if has_retention_days:
            retention_days = payload["retention_days"]
            if isinstance(retention_days, bool) or not isinstance(retention_days, int):
                raise ValueError("retention_days must be a positive integer")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope=("audit", "write"))
            self._json(
                store.set_query_retention_policy(
                    workspace_id,
                    user_id,
                    retention_days=None if clear else (retention_days if has_retention_days else _UNSET),
                    legal_hold=legal_hold if has_legal_hold else _UNSET,
                    legal_hold_reason=legal_hold_reason if has_legal_hold_reason else _UNSET,
                )
            )
        finally:
            store.close()

    def _get_provider_config(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            self._json(store.get_workspace_provider_config(workspace_id, user_id))
        finally:
            store.close()

    def _check_provider_config(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            self._json(store.check_workspace_provider_config(workspace_id, user_id))
        finally:
            store.close()

    def _probe_provider_config(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            self._json(store.probe_workspace_provider_config(workspace_id, user_id))
        finally:
            store.close()

    def _get_audit_sink_config(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            self._json(store.get_workspace_audit_jsonl_sink_config(workspace_id, user_id))
        finally:
            store.close()

    def _check_audit_sink(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            self._json(store.check_workspace_audit_jsonl_sink(workspace_id, user_id))
        finally:
            store.close()

    def _get_audit_sink_status(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            self._json(store.get_workspace_audit_jsonl_sink_status(workspace_id, user_id))
        finally:
            store.close()

    def _deployment_check(self, query: str) -> None:
        params = parse_qs(query)
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="audit", require_api_token=True)
            store.require_workspace_role(workspace_id, user_id, WORKSPACE_ADMIN_ROLES)
        finally:
            store.close()
        self._json(
            run_deployment_check(
                self.server.root,
                require_api_token=self.server.require_api_token,
                check_provider=_bool_param(params, "check_provider", False),
                require_provider_api_key=_bool_param(params, "require_provider_api_key", False),
                require_audit_sink=_bool_param(params, "require_audit_sink", False),
                require_audit_sink_format=_str_param(params, "require_audit_sink_format"),
            )
        )

    def _set_provider_config(self, payload: dict[str, Any]) -> None:
        clear = payload.get("clear", False)
        if not isinstance(clear, bool):
            raise ValueError("clear must be a boolean")
        has_updates = any(
            key in payload
            for key in ("base_url", "model", "api_key_env_var", "timeout_seconds")
        )
        if clear and has_updates:
            raise ValueError("choose clear or provider config fields")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            if clear:
                self._json(store.clear_workspace_provider_config(workspace_id, user_id))
                return
            base_url = payload.get("base_url")
            model = payload.get("model")
            if not isinstance(base_url, str) or not base_url.strip():
                raise ValueError("base_url is required")
            if not isinstance(model, str) or not model.strip():
                raise ValueError("model is required")
            self._json(
                store.set_workspace_provider_config(
                    workspace_id,
                    user_id,
                    base_url=base_url,
                    model=model,
                    api_key_env_var=_optional_str(payload.get("api_key_env_var"), "api_key_env_var"),
                    timeout_seconds=_optional_number(payload.get("timeout_seconds"), "timeout_seconds"),
                )
            )
        finally:
            store.close()

    def _set_audit_sink_config(self, payload: dict[str, Any]) -> None:
        clear = payload.get("clear", False)
        if not isinstance(clear, bool):
            raise ValueError("clear must be a boolean")
        has_updates = any(key in payload for key in ("relative_path", "path", "format", "enabled"))
        if clear and has_updates:
            raise ValueError("choose clear or audit sink fields")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            if clear:
                self._json(store.clear_workspace_audit_jsonl_sink_config(workspace_id, user_id))
                return
            relative_path = payload.get("relative_path", payload.get("path"))
            if not isinstance(relative_path, str) or not relative_path.strip():
                raise ValueError("relative_path is required")
            enabled = payload.get("enabled", True)
            if not isinstance(enabled, bool):
                raise ValueError("enabled must be a boolean")
            self._json(
                store.set_workspace_audit_jsonl_sink_config(
                    workspace_id,
                    user_id,
                    relative_path=relative_path,
                    format=_optional_str(payload.get("format"), "format"),
                    enabled=enabled,
                )
            )
        finally:
            store.close()

    def _purge_audit_retention(self, payload: dict[str, Any]) -> None:
        dry_run = payload.get("dry_run", False)
        if not isinstance(dry_run, bool):
            raise ValueError("dry_run must be a boolean")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope=("audit", "write"))
            self._json(store.purge_audit_events_by_retention(workspace_id, user_id, dry_run=dry_run))
        finally:
            store.close()

    def _purge_query_retention(self, payload: dict[str, Any]) -> None:
        dry_run = payload.get("dry_run", False)
        if not isinstance(dry_run, bool):
            raise ValueError("dry_run must be a boolean")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope=("audit", "write"))
            self._json(store.purge_query_runs_by_retention(workspace_id, user_id, dry_run=dry_run))
        finally:
            store.close()

    def _get_managed_upload_orphans(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope="audit",
                require_api_token=True,
            )
            self._json({"report": store.get_managed_upload_orphan_report(workspace_id, user_id)})
        finally:
            store.close()

    def _purge_managed_upload_orphans(self, payload: dict[str, Any]) -> None:
        dry_run = payload.get("dry_run", False)
        if not isinstance(dry_run, bool):
            raise ValueError("dry_run must be a boolean")
        required_scope: str | tuple[str, ...] = "audit" if dry_run else ("audit", "write")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=required_scope,
                require_api_token=True,
            )
            self._json(
                {
                    "report": store.get_managed_upload_orphan_report(
                        workspace_id,
                        user_id,
                        purge=not dry_run,
                    )
                }
            )
        finally:
            store.close()

    def _query(self, payload: dict[str, Any]) -> None:
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query is required")
        source_set_id = payload.get("source_set_id", payload.get("sourceSetId"))
        if source_set_id is not None and not isinstance(source_set_id, str):
            raise ValueError("source_set_id must be a string")
        folder_id = payload.get("folder_id", payload.get("folderId"))
        if folder_id is not None and not isinstance(folder_id, str):
            raise ValueError("folder_id must be a string")
        if folder_id and (source_set_id or payload.get("doc_ids") is not None):
            raise ValueError("use only one of doc_ids, source_set_id, or folder_id")
        if source_set_id and payload.get("doc_ids") is not None:
            raise ValueError("use doc_ids or source_set_id, not both")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(store, required_scope="read")
            self._json(
                store.query_corpus(
                    query,
                    doc_ids=_list_or_none(payload.get("doc_ids")),
                    source_set_id=source_set_id,
                    folder_id=folder_id,
                    expert_hints=_list_or_none(payload.get("expert_hints")),
                    workspace_id=workspace_id,
                    limit=int(payload.get("limit", 8)),
                    actor_user_id=user_id,
                )
            )
        finally:
            store.close()

    def _list_query_source_sets(self) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope="read", require_api_token=True
            )
            self._json({"source_sets": store.list_query_source_sets(workspace_id, user_id)})
        finally:
            store.close()

    def _create_query_source_set(self, payload: dict[str, Any]) -> None:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")
        description = payload.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError("description must be a string")
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            self._json(
                store.create_query_source_set(
                    workspace_id,
                    user_id,
                    name,
                    _list_or_none(payload.get("doc_ids")),
                    description=description,
                    shared=_bool_body_value(payload.get("shared"), "shared") if "shared" in payload else False,
                ),
                HTTPStatus.CREATED,
            )
        finally:
            store.close()

    def _update_query_source_set(self, source_set_id: str, payload: dict[str, Any]) -> None:
        name = _optional_str(payload.get("name"), "name") if "name" in payload else _UNSET
        description = _optional_str(payload.get("description"), "description") if "description" in payload else _UNSET
        doc_ids = _list_or_none(payload.get("doc_ids")) if "doc_ids" in payload else _UNSET
        shared = _bool_body_value(payload.get("shared"), "shared") if "shared" in payload else _UNSET
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            self._json(
                store.update_query_source_set(
                    workspace_id,
                    user_id,
                    source_set_id,
                    name=name,
                    description=description,
                    doc_ids=doc_ids,
                    shared=shared,
                )
            )
        finally:
            store.close()

    def _delete_query_source_set(self, source_set_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            self._json({"deleted": store.delete_query_source_set(workspace_id, user_id, source_set_id)})
        finally:
            store.close()

    def _list_query_source_set_share_links(self, source_set_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            self._json(
                {
                    "share_links": store.list_query_source_set_share_links(
                        workspace_id,
                        user_id,
                        source_set_id,
                    )
                }
            )
        finally:
            store.close()

    def _create_query_source_set_share_link(self, source_set_id: str, payload: dict[str, Any]) -> None:
        if payload.get("expires_at") is not None and payload.get("expires_in_days") is not None:
            raise ValueError("choose expires_at or expires_in_days")
        expires_at = _optional_str(payload.get("expires_at"), "expires_at")
        if payload.get("expires_in_days") is not None:
            expires_at = expires_at_from_days(_optional_positive_int(payload.get("expires_in_days"), "expires_in_days"))
        redact_content = (
            _bool_body_value(payload.get("redact_content"), "redact_content")
            if "redact_content" in payload
            else False
        )
        max_views = _optional_positive_int(payload.get("max_views"), "max_views") if "max_views" in payload else None
        password = _optional_str(payload.get("password"), "password") if "password" in payload else None
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            share_link = store.create_query_source_set_share_link(
                workspace_id,
                user_id,
                source_set_id,
                expires_at=expires_at,
                redact_content=redact_content,
                max_views=max_views,
                password=password,
            )
            if share_link is None:
                self._json({"error": "query source set not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json({"share_link": share_link}, HTTPStatus.CREATED)
        finally:
            store.close()

    def _revoke_query_source_set_share_link(self, share_link_id: str) -> None:
        store = EnterpriseStore(self.server.root)
        try:
            workspace_id, user_id = self._workspace_context(
                store, required_scope=("audit", "write"), require_api_token=True
            )
            revoked = store.revoke_query_source_set_share_link(workspace_id, user_id, share_link_id)
            self._json({"revoked": revoked})
        finally:
            store.close()

    def _public_source_set_share(self, token: str, query: str) -> None:
        params = parse_qs(query)
        document_limit = max(1, min(_int_param(params, "document_limit", 100), 500))
        password = _share_password_value(params, self.headers)
        store = EnterpriseStore(self.server.root)
        try:
            shared = store.resolve_query_source_set_share_link(
                token,
                password=password,
                document_limit=document_limit,
            )
            if shared is None:
                self._json({"error": "share link not found"}, HTTPStatus.NOT_FOUND)
                return
            wants_html = _share_response_wants_html(self.headers.get("Accept", ""), _str_param(params, "format"))
            recorded = store.record_query_source_set_share_link_view(
                token,
                password=password,
                response_format="html" if wants_html else "json",
                document_limit=document_limit,
            )
            if not recorded:
                self._json({"error": "share link not found"}, HTTPStatus.NOT_FOUND)
                return
            if wants_html:
                self._html(_render_public_source_set_share(shared))
                return
            self._json(shared)
        finally:
            store.close()

    def _chat_completion(self, payload: dict[str, Any]) -> None:
        if (
            payload.get("tools") is not None
            or payload.get("tool_choice") is not None
            or payload.get("functions") is not None
            or payload.get("function_call") is not None
        ):
            raise ValueError("tool calls are not supported")
        messages = _chat_messages(payload.get("messages"))
        query = _chat_completion_query(messages)
        model = _optional_str(payload.get("model"), "model") or "pageindex-deterministic"
        synthesis_mode = _chat_synthesis_mode(payload.get("pageindex_synthesis"))
        conversation_id = _chat_conversation_id(payload)
        limit = int(payload.get("limit", 8))
        if synthesis_mode == "provider":
            limit = max(1, min(limit, 8))
        store = EnterpriseStore(self.server.root)
        try:
            required_scope = ("read", "write") if synthesis_mode == "provider" or conversation_id else "read"
            workspace_id, user_id = self._workspace_context(
                store,
                required_scope=required_scope,
                require_api_token=synthesis_mode == "provider" or bool(conversation_id),
            )
            provider_options: dict[str, Any] = {"model": model}
            if synthesis_mode == "provider":
                store.require_workspace_role(workspace_id, user_id, WORKSPACE_WRITE_ROLES)
                provider_options = store.workspace_provider_request_options(workspace_id, model)
                model = provider_options["model"]
            conversation_metadata = None
            prepared_provider_chat = None
            if conversation_id:
                if synthesis_mode == "provider":
                    chat_result = store._prepare_chat_message(
                        conversation_id,
                        user_id,
                        _chat_latest_user_message(messages),
                        doc_ids=_chat_doc_ids(payload),
                        expert_hints=_list_or_none(payload.get("expert_hints")),
                        limit=limit,
                        expected_workspace_id=workspace_id,
                    )
                    prepared_provider_chat = chat_result
                else:
                    chat_result = store.chat_message(
                        conversation_id,
                        user_id,
                        _chat_latest_user_message(messages),
                        doc_ids=_chat_doc_ids(payload),
                        expert_hints=_list_or_none(payload.get("expert_hints")),
                        limit=limit,
                        expected_workspace_id=workspace_id,
                    )
                    conversation_metadata = _chat_conversation_metadata(chat_result)
                result = chat_result["result"]
                query = chat_result["retrieval"]["query"]
            else:
                result = store.query_corpus(
                    query,
                    doc_ids=_chat_doc_ids(payload),
                    expert_hints=_list_or_none(payload.get("expert_hints")),
                    workspace_id=workspace_id,
                    limit=limit,
                    actor_user_id=user_id,
                    scope_extra={
                        "chat_completion": {
                            "message_count": len(messages),
                            "model": model,
                            "synthesis_mode": synthesis_mode,
                        }
                    },
                    stored_query=CHAT_TRACE_QUERY,
                    redact_query_tree=True,
                )
            answer = result["answer"]
            synthesis = {"mode": "deterministic"}
            if synthesis_mode == "provider" and payload.get("stream") is not True:
                synthesized = synthesize_with_openai_compatible(
                    query,
                    result["hybrid_search"]["hits"],
                    **provider_options,
                )
                answer = synthesized["answer"]
                synthesis = synthesized["metadata"]
                if prepared_provider_chat is not None:
                    chat_result = store._complete_prepared_chat_message(prepared_provider_chat, answer)
                    conversation_metadata = _chat_conversation_metadata(chat_result)
            response_model = synthesis.get("model", model) if synthesis_mode == "provider" else model
            completion_id = f"chatcmpl_{uuid.uuid4().hex}"
            created = int(time.time())
            prompt_tokens = _rough_token_count(query)
            pageindex = {
                "run_id": result["run_id"],
                "citations": result["citations"],
                "trace": result["trace"],
                "verification": result["verification"],
                "synthesis": synthesis,
            }
            if conversation_metadata is not None:
                pageindex["conversation"] = conversation_metadata
            if payload.get("stream") is True:
                if synthesis_mode == "provider":
                    with open_openai_compatible_stream(
                        query,
                        result["hybrid_search"]["hits"],
                        **provider_options,
                    ) as provider_stream:
                        provider_chunks = provider_stream.chunks()
                        try:
                            first_part = next(provider_chunks)
                        except StopIteration as exc:
                            raise LLMProviderError("llm provider stream missing content") from exc
                        response_model = provider_stream.metadata.get("model", model)
                        pageindex["synthesis"] = provider_stream.metadata
                        on_complete = None
                        if prepared_provider_chat is not None:
                            on_complete = lambda final_answer: _chat_conversation_metadata(
                                store._complete_prepared_chat_message(prepared_provider_chat, final_answer)
                            )
                        self._event_stream_from_parts(
                            completion_id,
                            created,
                            response_model,
                            _prepend_part(first_part, provider_chunks),
                            prompt_tokens,
                            pageindex,
                            on_complete=on_complete,
                        )
                else:
                    self._event_stream_from_parts(
                        completion_id,
                        created,
                        response_model,
                        _stream_text_parts(answer),
                        prompt_tokens,
                        pageindex,
                    )
                return
            completion_tokens = _rough_token_count(answer)
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
            self._json(
                _chat_completion_response(
                    completion_id,
                    created,
                    response_model,
                    answer,
                    usage,
                    pageindex,
                )
            )
        finally:
            store.close()

    def _event_stream(self, payloads: list[dict[str, Any]]) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for payload in payloads:
            self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _event_stream_from_parts(
        self,
        completion_id: str,
        created: int,
        model: str,
        parts: Any,
        prompt_tokens: int,
        pageindex: dict[str, Any],
        *,
        on_complete: Any | None = None,
    ) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        answer_parts = []
        try:
            for part in parts:
                answer_parts.append(part)
                payload = _chat_completion_delta(completion_id, created, model, part)
                self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                self.wfile.flush()
        except LLMProviderError as exc:
            payload = {
                "error": {
                    "type": "provider_stream_error",
                    "message": str(exc),
                }
            }
            self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        answer = "".join(answer_parts)
        completion_tokens = _rough_token_count(answer)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        if on_complete is not None:
            try:
                conversation_metadata = on_complete(answer)
                if conversation_metadata is not None:
                    pageindex["conversation"] = conversation_metadata
            except Exception as exc:
                payload = {
                    "error": {
                        "type": "conversation_persist_error",
                        "message": str(exc),
                    }
                }
                self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                return
        final_payload = _chat_completion_final_chunk(completion_id, created, model, usage, pageindex)
        self.wfile.write(f"data: {json.dumps(final_payload)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _read_json(self) -> dict[str, Any]:
        length = _body_length(self.headers, MAX_JSON_BODY_BYTES, "request body too large")
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _read_multipart_file(self) -> dict[str, Any]:
        return self._read_multipart_files()[0]

    def _read_multipart_files(self) -> list[dict[str, Any]]:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("multipart/form-data is required")
        length = _body_length(self.headers, MAX_MULTIPART_BODY_BYTES, "multipart body too large")
        body = self.rfile.read(length)
        raw = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            + body
        )
        message = BytesParser(policy=default).parsebytes(raw)
        if not message.is_multipart():
            raise ValueError("multipart/form-data is required")
        fields: dict[str, str] = {}
        file_parts: list[dict[str, Any]] = []
        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue
            name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            content = part.get_payload(decode=True) or b""
            if name in {"file", "files"} and filename:
                file_parts.append({"filename": filename, "content": content})
            elif name:
                fields[name] = content.decode("utf-8", errors="replace").strip()
        if not file_parts:
            raise ValueError("file is required")
        if len(file_parts) > MAX_MULTIPART_FILES:
            raise ValueError(f"too many files; maximum is {MAX_MULTIPART_FILES}")
        if len(file_parts) == 1 and fields.get("name"):
            file_parts[0]["name"] = fields["name"]
        if fields.get("folder_id"):
            for file_part in file_parts:
                file_part["folder_id"] = fields["folder_id"]
        return file_parts

    def _workspace_context(
        self,
        store: EnterpriseStore,
        *,
        required_scope: str | tuple[str, ...] | None = None,
        require_api_token: bool = False,
    ) -> tuple[str, str]:
        auth_header = self.headers.get("Authorization", "").strip()
        if auth_header:
            scheme, _, token = auth_header.partition(" ")
            if scheme.casefold() == "bearer" and token.strip():
                verified = store.verify_api_token(token.strip())
                if not verified:
                    raise PermissionError("invalid api token")
                self.server.check_api_token_rate_limit(verified["id"])
                if any(scope not in verified["scopes"] for scope in _required_scopes(required_scope)):
                    raise PermissionError("api token scope denied")
                return verified["workspace_id"], verified["user_id"]
            if self.server.require_api_token or require_api_token:
                raise PermissionError("invalid api token")
        if self.server.require_api_token or require_api_token:
            raise PermissionError("api token required")
        workspace_id = self.headers.get("X-PageIndex-Workspace", "").strip()
        user_id = self.headers.get("X-PageIndex-User", "").strip()
        if not workspace_id or not user_id:
            raise PermissionError("workspace and user headers are required")
        try:
            store.require_workspace_access(workspace_id, user_id)
        except ValueError as exc:
            raise PermissionError("workspace access denied") from exc
        return workspace_id, user_id

    def _api_token_context(self, store: EnterpriseStore, *, required_scope: str | tuple[str, ...]) -> dict[str, Any]:
        auth_header = self.headers.get("Authorization", "").strip()
        if not auth_header:
            raise PermissionError("api token required")
        scheme, _, token = auth_header.partition(" ")
        if scheme.casefold() != "bearer" or not token.strip():
            raise PermissionError("invalid api token")
        verified = store.verify_api_token(token.strip())
        if not verified:
            raise PermissionError("invalid api token")
        self.server.check_api_token_rate_limit(verified["id"])
        if any(scope not in verified["scopes"] for scope in _required_scopes(required_scope)):
            raise PermissionError("api token scope denied")
        return verified

    def _rate_limit(self, exc: RateLimitError) -> None:
        self._json(
            {"error": str(exc), "retry_after_seconds": exc.retry_after_seconds},
            HTTPStatus.TOO_MANY_REQUESTS,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    def _json(
        self,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, payload: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, payload: str, status: HTTPStatus = HTTPStatus.OK, *, content_type: str = "text/plain; charset=utf-8") -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(
        self,
        payload: bytes,
        status: HTTPStatus = HTTPStatus.OK,
        *,
        content_type: str = "application/octet-stream",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)


def serve(
    root: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    require_api_token: bool = False,
    api_token_rate_limit: int | None = None,
    api_token_rate_window_seconds: float = 60.0,
) -> None:
    server = EnterpriseHTTPServer(
        (host, port),
        root,
        require_api_token=require_api_token,
        api_token_rate_limit=api_token_rate_limit,
        api_token_rate_window_seconds=api_token_rate_window_seconds,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _list_or_none(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("list value must contain strings")
    return value


def _required_scopes(required_scope: str | tuple[str, ...] | None) -> tuple[str, ...]:
    if required_scope is None:
        return ()
    if isinstance(required_scope, str):
        return (required_scope,)
    return tuple(required_scope)


def _chat_synthesis_mode(value: Any) -> str:
    if value is None:
        return "deterministic"
    if isinstance(value, str):
        mode = value.strip().casefold()
    elif isinstance(value, dict):
        raw_mode = value.get("mode", "deterministic")
        if not isinstance(raw_mode, str):
            raise ValueError("pageindex_synthesis.mode must be a string")
        mode = raw_mode.strip().casefold()
    else:
        raise ValueError("pageindex_synthesis must be a string or object")
    aliases = {
        "deterministic": "deterministic",
        "off": "deterministic",
        "none": "deterministic",
        "provider": "provider",
        "openai-compatible": "provider",
        "llm": "provider",
    }
    if mode not in aliases:
        raise ValueError("pageindex_synthesis mode must be deterministic or provider")
    return aliases[mode]


def _chat_doc_ids(payload: dict[str, Any]) -> list[str] | None:
    doc_id = payload.get("doc_id")
    doc_ids = payload.get("doc_ids")
    if doc_id is not None and doc_ids is not None:
        raise ValueError("use doc_id or doc_ids, not both")
    if doc_id is None:
        return _list_or_none(doc_ids)
    if isinstance(doc_id, str):
        return [doc_id]
    if isinstance(doc_id, list) and all(isinstance(item, str) for item in doc_id):
        return doc_id
    raise ValueError("doc_id must be a string or list of strings")


def _chat_conversation_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("conversation_id", payload.get("conversationId"))
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("conversation_id must be a string")
    value = value.strip()
    if not value:
        raise ValueError("conversation_id must be a string")
    return value


def _chat_conversation_metadata(chat_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": chat_result["conversation"]["id"],
        "title": chat_result["conversation"]["title"],
        "source_set_id": chat_result["conversation"].get("source_set_id"),
        "folder_id": chat_result["conversation"].get("folder_id"),
        "user_message_id": chat_result["user_message"]["id"],
        "assistant_message_id": chat_result["assistant_message"]["id"],
        "history_user_message_count": len(chat_result["retrieval"]["history_user_messages"]),
    }


def _chat_completion_response(
    completion_id: str,
    created: int,
    model: str,
    answer: str,
    usage: dict[str, int],
    pageindex: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
        "pageindex": pageindex,
    }


def _chat_completion_chunks(
    completion_id: str,
    created: int,
    model: str,
    answer: str,
    usage: dict[str, int],
    pageindex: dict[str, Any],
) -> list[dict[str, Any]]:
    return _chat_completion_chunks_from_parts(
        completion_id,
        created,
        model,
        _stream_text_parts(answer),
        usage,
        pageindex,
    )


def _chat_completion_chunks_from_parts(
    completion_id: str,
    created: int,
    model: str,
    parts: list[str],
    usage: dict[str, int],
    pageindex: dict[str, Any],
) -> list[dict[str, Any]]:
    chunks = []
    for part in parts:
        chunks.append(_chat_completion_delta(completion_id, created, model, part))
    chunks.append(_chat_completion_final_chunk(completion_id, created, model, usage, pageindex))
    return chunks


def _chat_completion_delta(completion_id: str, created: int, model: str, part: str) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": part},
                "finish_reason": None,
            },
        ],
    }


def _chat_completion_final_chunk(
    completion_id: str,
    created: int,
    model: str,
    usage: dict[str, int],
    pageindex: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": usage,
        "pageindex": pageindex,
    }


def _stream_text_parts(text: str) -> list[str]:
    words = text.split(" ")
    if not words:
        return [""]
    return [word + (" " if index < len(words) - 1 else "") for index, word in enumerate(words)]


def _prepend_part(first: str, rest: Any):
    yield first
    yield from rest


def _chat_messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise ValueError("messages must be a non-empty list")
    messages = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("messages must contain objects")
        role = item.get("role")
        content = item.get("content")
        if role not in {"system", "user", "assistant"}:
            raise ValueError("message role is not supported")
        if not isinstance(content, str):
            raise ValueError("message content must be a string")
        messages.append({"role": role, "content": content.strip()})
    if not any(message["role"] == "user" and message["content"] for message in messages):
        raise ValueError("at least one user message is required")
    return messages


def _chat_completion_query(messages: list[dict[str, str]]) -> str:
    user_messages = [message["content"] for message in messages if message["role"] == "user" and message["content"]]
    recent_context = user_messages[-4:-1]
    current = user_messages[-1]
    if not recent_context:
        return current
    return "\n".join([*recent_context, current])


def _chat_latest_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message["role"] == "user" and message["content"]:
            return message["content"]
    raise ValueError("at least one user message is required")


def _rough_token_count(value: str) -> int:
    return len([part for part in value.split() if part])


def _conversation_messages_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "conversations" and parts[2] == "messages":
        return parts[1]
    return None


def _conversation_archive_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "conversations" and parts[2] == "archive":
        return parts[1]
    return None


def _conversation_rename_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "conversations" and parts[2] == "rename":
        return parts[1]
    return None


def _conversation_scope_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "conversations" and parts[2] == "scope":
        return parts[1]
    return None


def _conversation_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "conversations":
        return parts[1]
    return None


def _conversation_export_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "conversations" and parts[2] == "export":
        return parts[1]
    return None


def _conversation_share_links_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "conversations" and parts[2] == "share-links":
        return unquote(parts[1])
    return None


def _conversation_share_link_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "conversation-share-links":
        return unquote(parts[1])
    return None


def _public_conversation_share_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "public" and parts[1] == "conversations":
        return unquote(parts[2])
    return None


def _document_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "documents":
        return parts[1]
    return None


def _document_rename_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "rename":
        return unquote(parts[1])
    return None


def _document_move_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "move":
        return unquote(parts[1])
    return None


def _document_reindex_upload_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "reindex-upload":
        return unquote(parts[1])
    return None


def _document_download_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "download":
        return unquote(parts[1])
    return None


def _document_questions_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "suggested-questions":
        return unquote(parts[1])
    return None


def _document_share_links_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "share-links":
        return unquote(parts[1])
    return None


def _document_share_link_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "document-share-links":
        return unquote(parts[1])
    return None


def _public_document_share_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "public" and parts[1] == "documents":
        return unquote(parts[2])
    return None


PUBLIC_SHARE_STYLE = """
    :root {
      color-scheme: light;
      --bg: #f8fafc;
      --text: #172033;
      --muted: #657189;
      --line: #d8dee9;
      --panel: #ffffff;
      --accent: #1d6f9f;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      max-width: 920px;
      margin: 0 auto;
      padding: 32px 18px 56px;
    }
    header {
      border-bottom: 1px solid var(--line);
      margin-bottom: 20px;
      padding-bottom: 16px;
    }
    h1 {
      font-size: clamp(28px, 5vw, 46px);
      line-height: 1.05;
      margin: 0 0 10px;
    }
    h2 {
      font-size: 17px;
      margin: 0 0 10px;
    }
    .muted,
    .meta {
      color: var(--muted);
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 16px;
      margin-top: 10px;
    }
    article,
    .empty {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 14px 0;
      padding: 16px;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
      font: inherit;
    }
    .role {
      color: var(--accent);
      font-weight: 700;
      text-transform: capitalize;
    }
    .citations {
      border-top: 1px solid var(--line);
      margin-top: 12px;
      padding-top: 10px;
    }
    .citations ul {
      margin: 6px 0 0 20px;
      padding: 0;
    }
"""


def _share_response_wants_html(accept_header: str, requested_format: str | None) -> bool:
    normalized_format = (requested_format or "").strip().casefold()
    if normalized_format == "html":
        return True
    if normalized_format == "json":
        return False
    normalized_accept = accept_header.casefold()
    return "text/html" in normalized_accept and "application/json" not in normalized_accept


def _html_value(value: Any) -> str:
    return html_escape("" if value is None else str(value), quote=True)


def _public_share_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_html_value(title)} - PageIndex</title>
  <style>{PUBLIC_SHARE_STYLE}</style>
</head>
<body>
{body}
</body>
</html>
"""


def _render_public_document_share(shared: dict[str, Any]) -> str:
    document = shared.get("document") or {}
    share_link = shared.get("share_link") or {}
    pages = shared.get("pages") or []
    title = str(document.get("name") or "Shared document")
    description = str(document.get("description") or "").strip()
    description_html = f'<p class="muted">{_html_value(description)}</p>' if description else ""
    page_cards = "\n".join(
        f"""
      <article>
        <h2>Page {_html_value(page.get("page"))}</h2>
        <pre>{_html_value(page.get("content"))}</pre>
        {'<p class="muted">Page content truncated.</p>' if page.get("truncated") else ''}
      </article>
        """
        for page in pages
    )
    if not page_cards:
        page_cards = '<p class="empty muted">No pages in this view.</p>'
    body = f"""
  <main>
    <header>
      <p class="muted">PageIndex shared document</p>
      <h1>{_html_value(title)}</h1>
      {description_html}
      <div class="meta">
        <span>{_html_value(document.get("kind") or "document")}</span>
        <span>{len(pages)} of {_html_value(shared.get("total_pages") or 0)} pages shown</span>
        <span>Expires {_html_value(share_link.get("expires_at") or "never")}</span>
      </div>
    </header>
    <section>
      {page_cards}
    </section>
  </main>
"""
    return _public_share_shell(title, body)


def _render_public_conversation_share(shared: dict[str, Any]) -> str:
    conversation = shared.get("conversation") or {}
    share_link = shared.get("share_link") or {}
    messages = shared.get("messages") or []
    citations_by_run = shared.get("citations") or {}
    title = str(conversation.get("title") or "Shared conversation")
    message_cards = []
    for message in messages:
        run_id = message.get("run_id")
        citations = citations_by_run.get(run_id, []) if run_id else []
        citation_html = ""
        if citations:
            items = "\n".join(
                (
                    f"<li>{_html_value(citation.get('doc_name') or citation.get('doc_id'))}"
                    f" - {_html_value(citation.get('label'))}</li>"
                )
                for citation in citations
            )
            citation_html = f'<div class="citations"><strong>Citations</strong><ul>{items}</ul></div>'
        message_cards.append(
            f"""
      <article>
        <div class="role">{_html_value(message.get("role") or "message")}</div>
        <pre>{_html_value(message.get("content"))}</pre>
        {citation_html}
      </article>
            """
        )
    messages_html = "\n".join(message_cards) if message_cards else '<p class="empty muted">No messages in this view.</p>'
    body = f"""
  <main>
    <header>
      <p class="muted">PageIndex shared conversation</p>
      <h1>{_html_value(title)}</h1>
      <div class="meta">
        <span>{len(messages)} messages shown</span>
        <span>Updated {_html_value(conversation.get("updated_at") or "unknown")}</span>
        <span>Expires {_html_value(share_link.get("expires_at") or "never")}</span>
      </div>
    </header>
    <section>
      {messages_html}
    </section>
  </main>
"""
    return _public_share_shell(title, body)


def _render_public_source_set_share(shared: dict[str, Any]) -> str:
    source_set = shared.get("source_set") or {}
    share_link = shared.get("share_link") or {}
    documents = shared.get("documents") or []
    title = str(source_set.get("name") or "Shared source set")
    description = str(source_set.get("description") or "").strip()
    description_html = f'<p class="muted">{_html_value(description)}</p>' if description else ""
    document_cards = "\n".join(
        f"""
      <article>
        <h2>{_html_value(document.get("name") or "Document")}</h2>
        <p class="muted">{_html_value(document.get("description") or "")}</p>
        <div class="meta">
          <span>{_html_value(document.get("kind") or "document")}</span>
          <span>{_html_value(document.get("page_count") or 0)} pages</span>
        </div>
      </article>
        """
        for document in documents
    )
    if not document_cards:
        document_cards = '<p class="empty muted">No documents in this view.</p>'
    body = f"""
  <main>
    <header>
      <p class="muted">PageIndex shared source set</p>
      <h1>{_html_value(title)}</h1>
      {description_html}
      <div class="meta">
        <span>{len(documents)} documents shown</span>
        <span>Updated {_html_value(source_set.get("updated_at") or "unknown")}</span>
        <span>Expires {_html_value(share_link.get("expires_at") or "never")}</span>
      </div>
    </header>
    <section>
      {document_cards}
    </section>
  </main>
"""
    return _public_share_shell(title, body)


def _query_run_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "query-runs":
        return unquote(parts[1])
    return None


def _query_source_set_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "query-source-sets":
        return unquote(parts[1])
    return None


def _query_source_set_share_links_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "query-source-sets" and parts[2] == "share-links":
        return unquote(parts[1])
    return None


def _query_source_set_share_link_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "query-source-set-share-links":
        return unquote(parts[1])
    return None


def _public_source_set_share_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "public" and parts[1] == "source-sets":
        return unquote(parts[2])
    return None


def _folder_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "folders":
        return unquote(parts[1])
    return None


def _folder_move_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "folders" and parts[2] == "move":
        return unquote(parts[1])
    return None


def _folder_access_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "folders" and parts[2] == "access":
        return unquote(parts[1])
    return None


def _document_access_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "access":
        return parts[1]
    return None


def _document_versions_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "versions":
        return parts[1]
    return None


def _document_pages_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "documents" and parts[2] == "pages":
        return parts[1]
    return None


def _workspace_member_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "workspace-members":
        return unquote(parts[1])
    return None


def _workspace_invitation_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "workspace-invitations":
        return unquote(parts[1])
    return None


def _workspace_group_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "workspace-groups":
        return unquote(parts[1])
    return None


def _workspace_group_members_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "workspace-groups" and parts[2] == "members":
        return unquote(parts[1])
    return None


def _workspace_group_member_path(path: str) -> tuple[str, str] | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 4 and parts[0] == "workspace-groups" and parts[2] == "members":
        return unquote(parts[1]), unquote(parts[3])
    return None


def _api_token_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 2 and parts[0] == "api-tokens":
        return unquote(parts[1])
    return None


def _api_token_rotate_path(path: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if len(parts) == 3 and parts[0] == "api-tokens" and parts[2] == "rotate":
        return unquote(parts[1])
    return None


def _optional_str(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _optional_positive_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _optional_number(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    return float(value)


def _bool_body_value(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _token_scopes_from_payload(value: Any, verified_scopes: list[str]) -> list[str]:
    if value is None:
        return list(verified_scopes)
    if not isinstance(value, list) or not all(isinstance(scope, str) for scope in value):
        raise ValueError("scopes must contain strings")
    normalized = {scope.strip().casefold() for scope in value if scope.strip()}
    if not normalized:
        raise ValueError("At least one api token scope is required.")
    unsupported = sorted(normalized - set(API_TOKEN_SCOPES))
    if unsupported:
        raise ValueError(f"Unsupported api token scope: {unsupported[0]}")
    scopes = [scope for scope in API_TOKEN_SCOPES if scope in normalized]
    _require_scopes_within_token(scopes, verified_scopes)
    return scopes


def _require_scopes_within_token(requested_scopes: list[str], verified_scopes: list[str]) -> None:
    if any(scope not in verified_scopes for scope in requested_scopes):
        raise PermissionError("api token scope denied")


def _find_token_metadata(tokens: list[dict[str, Any]], token_id: str) -> dict[str, Any] | None:
    for token in tokens:
        if token["id"] == token_id:
            return token
    return None


def _safe_upload_filename(filename: str) -> str:
    name = Path(filename).name
    safe = "".join(char if char.isalnum() or char in ".-_" else "_" for char in name).strip(" ._")
    return safe or "upload.bin"


def _safe_download_filename(filename: str, fallback_name: str) -> str:
    safe = _safe_upload_filename(filename)
    fallback = _safe_upload_filename(fallback_name)
    fallback_suffix = Path(fallback).suffix
    if fallback_suffix and not Path(safe).suffix:
        safe = f"{safe}{fallback_suffix}"
    return safe


def _safe_path_segment(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in ".-_" else "_" for char in value).strip(" ._")
    return safe or "workspace"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _int_param(params: dict[str, list[str]], name: str, default: int) -> int:
    values = params.get(name)
    return int(values[0]) if values else default


def _str_param(params: dict[str, list[str]], name: str, default: str | None = None) -> str | None:
    values = params.get(name)
    if not values:
        return default
    return values[0]


def _share_password_value(params: dict[str, list[str]], headers: Any) -> str | None:
    header_password = headers.get("X-PageIndex-Share-Password")
    if header_password is not None:
        return header_password
    return _str_param(params, "password")


def _bool_param(params: dict[str, list[str]], name: str, default: bool) -> bool:
    values = params.get(name)
    if not values:
        return default
    value = values[0].strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be boolean")


def _body_length(headers: Any, max_bytes: int, too_large_message: str) -> int:
    length = int(headers.get("Content-Length") or 0)
    if length < 0:
        raise ValueError("content length is invalid")
    if length > max_bytes:
        raise ValueError(too_large_message)
    return length
