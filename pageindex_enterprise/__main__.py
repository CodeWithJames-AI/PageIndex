from __future__ import annotations

import argparse
import json

from .deployment import run_deployment_check
from .eval import run_enterprise_eval
from .server import serve
from .store import (
    API_TOKEN_SCOPES,
    EnterpriseStore,
    _UNSET,
    _redacted_audit_export_events,
    expires_at_from_days,
    validate_workspace_import_bundle,
)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be numeric") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _conversation_cli(action):
    try:
        return action()
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc


def _workspace_member_cli(action):
    try:
        return action()
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc


def _api_token_cli(action):
    try:
        return action()
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc


def _folder_cli(action):
    try:
        return action()
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc


def _delete_document_cli(action):
    try:
        deleted = action()
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc
    if not deleted:
        raise SystemExit("document not found")
    return deleted


def _reindex_document_cli(action):
    try:
        document = action()
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc
    if document is None:
        raise SystemExit("document not found")
    return document


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m pageindex_enterprise")
    parser.add_argument("--root", default=".pageindex-enterprise")
    sub = parser.add_subparsers(dest="command", required=True)

    folder = sub.add_parser("folder")
    folder.add_argument("name")
    folder.add_argument("--parent-id")
    folder.add_argument("--workspace-id")
    folder.add_argument("--user-id")

    rename_folder = sub.add_parser("rename-folder")
    rename_folder.add_argument("folder_id")
    rename_folder.add_argument("name")
    rename_folder.add_argument("--workspace-id")
    rename_folder.add_argument("--user-id")

    delete_folder = sub.add_parser("delete-folder")
    delete_folder.add_argument("folder_id")
    delete_folder.add_argument("--workspace-id")
    delete_folder.add_argument("--user-id")

    move_folder = sub.add_parser("move-folder")
    move_folder.add_argument("folder_id")
    move_folder.add_argument("--parent-id")
    move_folder.add_argument("--workspace-id")
    move_folder.add_argument("--user-id")

    workspace = sub.add_parser("workspace")
    workspace.add_argument("name")
    workspace.add_argument("--workspace-id")

    member = sub.add_parser("add-member")
    member.add_argument("workspace_id")
    member.add_argument("user_id")
    member.add_argument("--role", default="member")
    member.add_argument("--actor-user-id")

    list_members = sub.add_parser("list-members")
    list_members.add_argument("workspace_id")
    list_members.add_argument("actor_user_id")

    workspace_usage = sub.add_parser("workspace-usage")
    workspace_usage.add_argument("workspace_id")
    workspace_usage.add_argument("actor_user_id")

    workspace_quota_policy = sub.add_parser("workspace-quota-policy")
    workspace_quota_policy.add_argument("workspace_id")
    workspace_quota_policy.add_argument("user_id")
    workspace_quota_policy.add_argument("--max-documents", type=_positive_int)
    workspace_quota_policy.add_argument("--clear-documents", action="store_true")
    workspace_quota_policy.add_argument("--max-pages", type=_positive_int)
    workspace_quota_policy.add_argument("--clear-pages", action="store_true")
    workspace_quota_policy.add_argument("--max-members", type=_positive_int)
    workspace_quota_policy.add_argument("--clear-members", action="store_true")

    remove_member = sub.add_parser("remove-member")
    remove_member.add_argument("workspace_id")
    remove_member.add_argument("user_id")
    remove_member.add_argument("actor_user_id")

    create_group = sub.add_parser("create-group")
    create_group.add_argument("workspace_id")
    create_group.add_argument("actor_user_id")
    create_group.add_argument("name")

    list_groups = sub.add_parser("list-groups")
    list_groups.add_argument("workspace_id")
    list_groups.add_argument("actor_user_id")

    rename_group = sub.add_parser("rename-group")
    rename_group.add_argument("workspace_id")
    rename_group.add_argument("actor_user_id")
    rename_group.add_argument("group_id")
    rename_group.add_argument("name")

    delete_group = sub.add_parser("delete-group")
    delete_group.add_argument("workspace_id")
    delete_group.add_argument("actor_user_id")
    delete_group.add_argument("group_id")

    add_group_member = sub.add_parser("add-group-member")
    add_group_member.add_argument("workspace_id")
    add_group_member.add_argument("actor_user_id")
    add_group_member.add_argument("group_id")
    add_group_member.add_argument("user_id")

    remove_group_member = sub.add_parser("remove-group-member")
    remove_group_member.add_argument("workspace_id")
    remove_group_member.add_argument("actor_user_id")
    remove_group_member.add_argument("group_id")
    remove_group_member.add_argument("user_id")

    list_group_members = sub.add_parser("list-group-members")
    list_group_members.add_argument("workspace_id")
    list_group_members.add_argument("actor_user_id")
    list_group_members.add_argument("group_id")

    invite_member = sub.add_parser("invite-member")
    invite_member.add_argument("workspace_id")
    invite_member.add_argument("actor_user_id")
    invite_member.add_argument("email")
    invite_member.add_argument("--role", default="member")
    invite_member.add_argument("--expires-in-days", type=_positive_int)

    list_invitations = sub.add_parser("list-invitations")
    list_invitations.add_argument("workspace_id")
    list_invitations.add_argument("actor_user_id")
    list_invitations.add_argument("--status", choices=["pending", "accepted", "revoked", "expired"])

    accept_invitation = sub.add_parser("accept-invitation")
    accept_invitation.add_argument("invitation_id")
    accept_invitation.add_argument("user_id")

    revoke_invitation = sub.add_parser("revoke-invitation")
    revoke_invitation.add_argument("workspace_id")
    revoke_invitation.add_argument("actor_user_id")
    revoke_invitation.add_argument("invitation_id")

    token = sub.add_parser("create-token")
    token.add_argument("workspace_id")
    token.add_argument("user_id")
    token.add_argument("--name", default="default")
    token.add_argument("--expires-in-days", type=_positive_int)
    token.add_argument("--scope", action="append", choices=API_TOKEN_SCOPES, dest="scopes")

    list_tokens = sub.add_parser("list-tokens")
    list_tokens.add_argument("workspace_id")
    list_tokens.add_argument("user_id")

    revoke_token = sub.add_parser("revoke-token")
    revoke_token.add_argument("workspace_id")
    revoke_token.add_argument("user_id")
    revoke_token.add_argument("token_id")

    rotate_token = sub.add_parser("rotate-token")
    rotate_token.add_argument("workspace_id")
    rotate_token.add_argument("user_id")
    rotate_token.add_argument("token_id")

    token_policy = sub.add_parser("token-policy")
    token_policy.add_argument("workspace_id")
    token_policy.add_argument("user_id")
    token_policy.add_argument("--default-expires-in-days", type=_positive_int)
    token_policy.add_argument("--clear-default-expiration", action="store_true")
    token_policy.add_argument("--rotation-due-in-days", type=_positive_int)
    token_policy.add_argument("--clear-rotation-due", action="store_true")

    provider_config = sub.add_parser("provider-config")
    provider_config.add_argument("workspace_id")
    provider_config.add_argument("user_id")
    provider_config.add_argument("--base-url")
    provider_config.add_argument("--model")
    provider_config.add_argument("--api-key-env-var")
    provider_config.add_argument("--timeout-seconds", type=_positive_float)
    provider_config.add_argument("--clear", action="store_true")
    provider_config.add_argument("--check", action="store_true")
    provider_config.add_argument("--probe", action="store_true")

    audit_sink = sub.add_parser("audit-sink")
    audit_sink.add_argument("workspace_id")
    audit_sink.add_argument("user_id")
    audit_sink.add_argument("--relative-path")
    audit_sink.add_argument("--format", choices=["jsonl", "siem-jsonl"])
    audit_sink.add_argument("--disable", action="store_true")
    audit_sink.add_argument("--clear", action="store_true")
    audit_sink.add_argument("--check", action="store_true")
    audit_sink.add_argument("--status", action="store_true")

    workspace_export = sub.add_parser("workspace-export")
    workspace_export.add_argument("workspace_id")
    workspace_export.add_argument("user_id")
    workspace_export.add_argument("output_path")

    workspace_import = sub.add_parser("workspace-import")
    workspace_import.add_argument("bundle_path")
    workspace_import.add_argument("--dry-run", action="store_true")

    audit_log = sub.add_parser("audit-log")
    audit_log.add_argument("workspace_id")
    audit_log.add_argument("user_id")
    audit_log.add_argument("--limit", type=int, default=100)
    audit_log.add_argument("--since")
    audit_log.add_argument("--until")
    audit_log.add_argument("--action")
    audit_log.add_argument("--event-user-id")
    audit_log.add_argument("--target-type")
    audit_log.add_argument("--target-id")

    audit_export = sub.add_parser("audit-export")
    audit_export.add_argument("workspace_id")
    audit_export.add_argument("user_id")
    audit_export.add_argument("--limit", type=int, default=500)
    audit_export.add_argument("--since")
    audit_export.add_argument("--until")
    audit_export.add_argument("--action")
    audit_export.add_argument("--event-user-id")
    audit_export.add_argument("--target-type")
    audit_export.add_argument("--target-id")
    audit_export.add_argument("--format", choices=["jsonl", "csv", "siem-jsonl"], default="jsonl")

    audit_integrity = sub.add_parser("audit-integrity")
    audit_integrity.add_argument("workspace_id")
    audit_integrity.add_argument("user_id")

    audit_retention = sub.add_parser("audit-retention")
    audit_retention.add_argument("workspace_id")
    audit_retention.add_argument("user_id")
    audit_retention.add_argument("--retention-days", type=_positive_int)
    audit_retention.add_argument("--clear", action="store_true")
    audit_retention.add_argument("--legal-hold", action="store_true")
    audit_retention.add_argument("--clear-legal-hold", action="store_true")
    audit_retention.add_argument("--legal-hold-reason")

    audit_purge = sub.add_parser("audit-purge")
    audit_purge.add_argument("workspace_id")
    audit_purge.add_argument("user_id")
    audit_purge.add_argument("--dry-run", action="store_true")

    query_retention = sub.add_parser("query-retention")
    query_retention.add_argument("workspace_id")
    query_retention.add_argument("user_id")
    query_retention.add_argument("--retention-days", type=_positive_int)
    query_retention.add_argument("--clear", action="store_true")
    query_retention.add_argument("--legal-hold", action="store_true")
    query_retention.add_argument("--clear-legal-hold", action="store_true")
    query_retention.add_argument("--legal-hold-reason")

    query_purge = sub.add_parser("query-purge")
    query_purge.add_argument("workspace_id")
    query_purge.add_argument("user_id")
    query_purge.add_argument("--dry-run", action="store_true")

    query_export = sub.add_parser("query-export")
    query_export.add_argument("workspace_id")
    query_export.add_argument("user_id")
    query_export.add_argument("--limit", type=int, default=500)
    query_export.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")
    query_export.add_argument("--actor-user-id")
    query_export.add_argument("--since")
    query_export.add_argument("--until")
    query_export.add_argument("--query")

    delete_query_run = sub.add_parser("delete-query-run")
    delete_query_run.add_argument("workspace_id")
    delete_query_run.add_argument("user_id")
    delete_query_run.add_argument("run_id")

    create_conversation = sub.add_parser("create-conversation")
    create_conversation.add_argument("workspace_id")
    create_conversation.add_argument("user_id")
    create_conversation.add_argument("--title")
    create_conversation.add_argument("--source-set-id")
    create_conversation.add_argument("--folder-id")

    list_conversations = sub.add_parser("list-conversations")
    list_conversations.add_argument("workspace_id")
    list_conversations.add_argument("user_id")
    list_conversations.add_argument("--limit", type=int, default=50)
    list_conversations.add_argument("--include-archived", action="store_true")

    archive_conversation = sub.add_parser("archive-conversation")
    archive_conversation.add_argument("conversation_id")
    archive_conversation.add_argument("user_id")
    archive_conversation.add_argument("--restore", action="store_true")

    rename_conversation = sub.add_parser("rename-conversation")
    rename_conversation.add_argument("conversation_id")
    rename_conversation.add_argument("user_id")
    rename_conversation.add_argument("title")

    set_conversation_scope = sub.add_parser("set-conversation-scope")
    set_conversation_scope.add_argument("conversation_id")
    set_conversation_scope.add_argument("user_id")
    set_conversation_scope.add_argument("--source-set-id")
    set_conversation_scope.add_argument("--folder-id")
    set_conversation_scope.add_argument("--clear", action="store_true")

    delete_conversation = sub.add_parser("delete-conversation")
    delete_conversation.add_argument("conversation_id")
    delete_conversation.add_argument("user_id")

    conversation_messages = sub.add_parser("conversation-messages")
    conversation_messages.add_argument("conversation_id")
    conversation_messages.add_argument("user_id")
    conversation_messages.add_argument("--limit", type=int, default=100)

    export_conversation = sub.add_parser("export-conversation")
    export_conversation.add_argument("conversation_id")
    export_conversation.add_argument("user_id")
    export_conversation.add_argument("--limit", type=int, default=500)
    export_conversation.add_argument("--format", choices=["jsonl", "markdown"], default="jsonl")

    conversation_share = sub.add_parser("conversation-share")
    conversation_share.add_argument("workspace_id")
    conversation_share.add_argument("user_id")
    conversation_share.add_argument("--share")
    conversation_share.add_argument("--shares")
    conversation_share.add_argument("--revoke-share")
    conversation_share.add_argument("--share-redact", action="store_true")
    conversation_share.add_argument("--share-expires-at")
    conversation_share.add_argument("--share-expires-in-days", type=_positive_int)
    conversation_share.add_argument("--share-max-views", type=_positive_int)
    conversation_share.add_argument("--share-password")

    chat_message = sub.add_parser("chat-message")
    chat_message.add_argument("conversation_id")
    chat_message.add_argument("user_id")
    chat_message.add_argument("message")
    chat_message.add_argument("--doc-id", action="append", dest="doc_ids")
    chat_message.add_argument("--hint", action="append", dest="expert_hints")
    chat_message.add_argument("--limit", type=int, default=8)

    doc = sub.add_parser("register-doc")
    doc.add_argument("name")
    doc.add_argument("source_path")
    doc.add_argument("--kind", default="pdf")
    doc.add_argument("--description", default="")
    doc.add_argument("--folder-id")
    doc.add_argument("--workspace-id")
    doc.add_argument("--user-id")
    doc.add_argument("--page-count", type=int)

    delete_doc = sub.add_parser("delete-doc")
    delete_doc.add_argument("doc_id")
    delete_doc.add_argument("--workspace-id")
    delete_doc.add_argument("--user-id")

    rename_doc = sub.add_parser("rename-doc")
    rename_doc.add_argument("doc_id")
    rename_doc.add_argument("name")
    rename_doc.add_argument("--workspace-id")
    rename_doc.add_argument("--user-id")

    move_doc = sub.add_parser("move-doc")
    move_doc.add_argument("doc_id")
    move_doc.add_argument("--folder-id")
    move_doc.add_argument("--clear-folder", action="store_true")
    move_doc.add_argument("--workspace-id")
    move_doc.add_argument("--user-id")

    reindex_doc = sub.add_parser("reindex-doc")
    reindex_doc.add_argument("doc_id")
    reindex_doc.add_argument("path")
    reindex_doc.add_argument("--name")
    reindex_doc.add_argument("--folder-id")
    reindex_doc.add_argument("--workspace-id")
    reindex_doc.add_argument("--user-id")

    doc_versions = sub.add_parser("document-versions")
    doc_versions.add_argument("doc_id")
    doc_versions.add_argument("--workspace-id")
    doc_versions.add_argument("--user-id")
    doc_versions.add_argument("--limit", type=int, default=100)

    document_access = sub.add_parser("document-access")
    document_access.add_argument("doc_id")
    document_access.add_argument("workspace_id")
    document_access.add_argument("actor_user_id")
    document_access.add_argument("--mode", choices=["workspace", "restricted"])
    document_access.add_argument("--grant-user")
    document_access.add_argument("--revoke-user")
    document_access.add_argument("--grant-group")
    document_access.add_argument("--revoke-group")
    document_access.add_argument("--role", choices=["read", "write", "deny"], default="read")

    acl_bulk = sub.add_parser("acl-bulk")
    acl_bulk.add_argument("workspace_id")
    acl_bulk.add_argument("actor_user_id")
    acl_bulk.add_argument("policy_path")
    acl_bulk.add_argument("--apply", action="store_true")

    document_share = sub.add_parser("document-share")
    document_share.add_argument("workspace_id")
    document_share.add_argument("user_id")
    document_share.add_argument("--share")
    document_share.add_argument("--shares")
    document_share.add_argument("--revoke-share")
    document_share.add_argument("--share-redact", action="store_true")
    document_share.add_argument("--share-expires-at")
    document_share.add_argument("--share-expires-in-days", type=_positive_int)
    document_share.add_argument("--share-max-views", type=_positive_int)
    document_share.add_argument("--share-password")

    ingest = sub.add_parser("ingest-file")
    ingest.add_argument("path")
    ingest.add_argument("--name")
    ingest.add_argument("--folder-id")
    ingest.add_argument("--workspace-id")
    ingest.add_argument("--user-id")

    structure = sub.add_parser("import-structure")
    structure.add_argument("path")
    structure.add_argument("--doc-id")
    structure.add_argument("--folder-id")
    structure.add_argument("--workspace-id")
    structure.add_argument("--user-id")

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--workspace-id")
    search.add_argument("--user-id")
    search.add_argument("--limit", type=int, default=20)

    query = sub.add_parser("query")
    query.add_argument("query")
    query.add_argument("--doc-id", action="append", dest="doc_ids")
    query.add_argument("--source-set-id")
    query.add_argument("--folder-id")
    query.add_argument("--hint", action="append", dest="expert_hints")
    query.add_argument("--workspace-id")
    query.add_argument("--user-id")
    query.add_argument("--limit", type=int, default=8)

    query_source_set = sub.add_parser("query-source-set")
    query_source_set.add_argument("workspace_id")
    query_source_set.add_argument("user_id")
    query_source_set.add_argument("--create")
    query_source_set.add_argument("--update")
    query_source_set.add_argument("--name")
    query_source_set.add_argument("--description")
    query_source_set.add_argument("--doc-id", action="append", dest="doc_ids")
    query_source_set.add_argument("--shared", action="store_true")
    query_source_set.add_argument("--private", action="store_true")
    query_source_set.add_argument("--delete")
    query_source_set.add_argument("--share")
    query_source_set.add_argument("--shares")
    query_source_set.add_argument("--revoke-share")
    query_source_set.add_argument("--share-redact", action="store_true")
    query_source_set.add_argument("--share-expires-at")
    query_source_set.add_argument("--share-expires-in-days", type=_positive_int)
    query_source_set.add_argument("--share-max-views", type=_positive_int)
    query_source_set.add_argument("--share-password")

    query_tree = sub.add_parser("query-tree")
    query_tree.add_argument("query")
    query_tree.add_argument("--doc-id", action="append", dest="doc_ids")
    query_tree.add_argument("--hint", action="append", dest="expert_hints")
    query_tree.add_argument("--workspace-id")
    query_tree.add_argument("--user-id")
    query_tree.add_argument("--limit", type=int, default=8)

    hybrid = sub.add_parser("hybrid-search")
    hybrid.add_argument("query")
    hybrid.add_argument("--doc-id", action="append", dest="doc_ids")
    hybrid.add_argument("--hint", action="append", dest="expert_hints")
    hybrid.add_argument("--workspace-id")
    hybrid.add_argument("--user-id")
    hybrid.add_argument("--limit", type=int, default=8)

    trace = sub.add_parser("verify-trace")
    trace.add_argument("run_id")

    sub.add_parser("rebuild-virtual-index")

    virtual = sub.add_parser("virtual-nodes")
    virtual.add_argument("--query")
    virtual.add_argument("--workspace-id")

    serve_cmd = sub.add_parser("serve")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8765)
    serve_cmd.add_argument("--require-api-token", action="store_true")
    serve_cmd.add_argument("--api-token-rate-limit", type=_positive_int)
    serve_cmd.add_argument("--api-token-rate-window-seconds", type=_positive_float, default=60.0)

    eval_cmd = sub.add_parser("eval")
    eval_cmd.add_argument("--fixtures-root")

    deployment_check = sub.add_parser("deployment-check")
    deployment_check.add_argument("--require-api-token", action="store_true")
    deployment_check.add_argument("--check-provider", action="store_true")
    deployment_check.add_argument("--require-provider-api-key", action="store_true")
    deployment_check.add_argument("--require-audit-sink", action="store_true")
    deployment_check.add_argument("--require-audit-sink-format", choices=["jsonl", "siem-jsonl"])
    deployment_check.add_argument("--fail-on-unready", action="store_true")

    args = parser.parse_args()
    if args.command == "serve":
        serve(
            args.root,
            host=args.host,
            port=args.port,
            require_api_token=args.require_api_token,
            api_token_rate_limit=args.api_token_rate_limit,
            api_token_rate_window_seconds=args.api_token_rate_window_seconds,
        )
        return
    if args.command == "eval":
        print(json.dumps(run_enterprise_eval(args.root, fixtures_root=args.fixtures_root), indent=2))
        return
    if args.command == "deployment-check":
        report = run_deployment_check(
            args.root,
            require_api_token=args.require_api_token,
            check_provider=args.check_provider,
            require_provider_api_key=args.require_provider_api_key,
            require_audit_sink=args.require_audit_sink,
            require_audit_sink_format=args.require_audit_sink_format,
        )
        print(json.dumps(report, indent=2))
        if args.fail_on_unready and not report.get("ok"):
            raise SystemExit(1)
        return
    if args.command == "workspace-import":
        if args.dry_run:
            print(json.dumps(validate_workspace_import_bundle(args.bundle_path), indent=2))
            return
        store = EnterpriseStore(args.root)
        try:
            try:
                print(json.dumps(store.import_workspace_bundle(args.bundle_path), indent=2))
            except (PermissionError, ValueError, FileNotFoundError) as exc:
                raise SystemExit(str(exc)) from exc
        finally:
            store.close()
        return

    store = EnterpriseStore(args.root)
    try:
        if args.command == "folder":
            print(
                _folder_cli(
                    lambda: store.create_folder(
                        args.name,
                        args.parent_id,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.user_id,
                    )
                )
            )
        elif args.command == "rename-folder":
            renamed_folder = _folder_cli(
                lambda: store.rename_folder(
                    args.folder_id,
                    args.name,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
                )
            )
            if renamed_folder is None:
                raise SystemExit("folder not found")
            print(json.dumps(renamed_folder, indent=2))
        elif args.command == "delete-folder":
            deleted = _folder_cli(
                lambda: store.delete_folder(
                    args.folder_id,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
                )
            )
            print(json.dumps({"deleted": deleted}))
        elif args.command == "move-folder":
            moved_folder = _folder_cli(
                lambda: store.move_folder(
                    args.folder_id,
                    parent_id=args.parent_id,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
                )
            )
            if moved_folder is None:
                raise SystemExit("folder not found")
            print(json.dumps(moved_folder, indent=2))
        elif args.command == "workspace":
            print(store.create_workspace(args.name, workspace_id=args.workspace_id))
        elif args.command == "add-member":
            _workspace_member_cli(
                lambda: store.add_workspace_member(
                    args.workspace_id,
                    args.user_id,
                    args.role,
                    actor_user_id=args.actor_user_id,
                )
            )
            print(json.dumps({"ok": True}))
        elif args.command == "list-members":
            print(
                json.dumps(
                    _workspace_member_cli(
                        lambda: store.list_workspace_members(args.workspace_id, args.actor_user_id)
                    ),
                    indent=2,
                )
            )
        elif args.command == "workspace-usage":
            print(
                json.dumps(
                    _workspace_member_cli(
                        lambda: store.get_workspace_usage_summary(args.workspace_id, args.actor_user_id)
                    ),
                    indent=2,
                )
            )
        elif args.command == "workspace-quota-policy":
            if args.max_documents is not None and args.clear_documents:
                raise SystemExit("use --max-documents or --clear-documents, not both")
            if args.max_pages is not None and args.clear_pages:
                raise SystemExit("use --max-pages or --clear-pages, not both")
            if args.max_members is not None and args.clear_members:
                raise SystemExit("use --max-members or --clear-members, not both")
            updates = {}
            if args.max_documents is not None:
                updates["max_documents"] = args.max_documents
            elif args.clear_documents:
                updates["max_documents"] = None
            if args.max_pages is not None:
                updates["max_pages"] = args.max_pages
            elif args.clear_pages:
                updates["max_pages"] = None
            if args.max_members is not None:
                updates["max_members"] = args.max_members
            elif args.clear_members:
                updates["max_members"] = None
            if updates:
                policy = _workspace_member_cli(
                    lambda: store.set_workspace_quota_policy(args.workspace_id, args.user_id, **updates)
                )
            else:
                policy = _workspace_member_cli(
                    lambda: store.get_workspace_quota_policy(args.workspace_id, args.user_id)
                )
            print(json.dumps(policy, indent=2))
        elif args.command == "remove-member":
            print(
                json.dumps(
                    {
                        "removed": _workspace_member_cli(
                            lambda: store.remove_workspace_member(
                                args.workspace_id,
                                args.user_id,
                                args.actor_user_id,
                            )
                        )
                    }
                )
            )
        elif args.command == "create-group":
            group = _workspace_member_cli(
                lambda: store.create_workspace_group(args.workspace_id, args.actor_user_id, args.name)
            )
            print(json.dumps(group, indent=2))
        elif args.command == "list-groups":
            groups = _workspace_member_cli(
                lambda: store.list_workspace_groups(args.workspace_id, args.actor_user_id)
            )
            print(json.dumps(groups, indent=2))
        elif args.command == "rename-group":
            group = _workspace_member_cli(
                lambda: store.rename_workspace_group(
                    args.workspace_id,
                    args.actor_user_id,
                    args.group_id,
                    args.name,
                )
            )
            print(json.dumps(group, indent=2))
        elif args.command == "delete-group":
            deleted = _workspace_member_cli(
                lambda: store.delete_workspace_group(
                    args.workspace_id,
                    args.actor_user_id,
                    args.group_id,
                )
            )
            print(json.dumps({"deleted": deleted}))
        elif args.command == "add-group-member":
            group = _workspace_member_cli(
                lambda: store.add_workspace_group_member(
                    args.workspace_id,
                    args.actor_user_id,
                    args.group_id,
                    args.user_id,
                )
            )
            print(json.dumps(group, indent=2))
        elif args.command == "remove-group-member":
            removed = _workspace_member_cli(
                lambda: store.remove_workspace_group_member(
                    args.workspace_id,
                    args.actor_user_id,
                    args.group_id,
                    args.user_id,
                )
            )
            print(json.dumps({"removed": removed}))
        elif args.command == "list-group-members":
            members = _workspace_member_cli(
                lambda: store.list_workspace_group_members(
                    args.workspace_id,
                    args.actor_user_id,
                    args.group_id,
                )
            )
            print(json.dumps(members, indent=2))
        elif args.command == "invite-member":
            invitation = _workspace_member_cli(
                lambda: store.create_workspace_invitation(
                    args.workspace_id,
                    args.actor_user_id,
                    args.email,
                    role=args.role,
                    expires_at=expires_at_from_days(args.expires_in_days),
                )
            )
            print(json.dumps(invitation, indent=2))
        elif args.command == "list-invitations":
            invitations = _workspace_member_cli(
                lambda: store.list_workspace_invitations(
                    args.workspace_id,
                    args.actor_user_id,
                    status=args.status,
                )
            )
            print(json.dumps(invitations, indent=2))
        elif args.command == "accept-invitation":
            invitation = _workspace_member_cli(
                lambda: store.accept_workspace_invitation(args.invitation_id, args.user_id)
            )
            print(json.dumps(invitation, indent=2))
        elif args.command == "revoke-invitation":
            revoked = _workspace_member_cli(
                lambda: store.revoke_workspace_invitation(
                    args.workspace_id,
                    args.actor_user_id,
                    args.invitation_id,
                )
            )
            print(json.dumps({"revoked": revoked}))
        elif args.command == "create-token":
            print(
                json.dumps(
                    _api_token_cli(
                        lambda: store.create_api_token(
                            args.workspace_id,
                            args.user_id,
                            args.name,
                            expires_at=expires_at_from_days(args.expires_in_days),
                            scopes=args.scopes,
                        )
                    ),
                    indent=2,
                )
            )
        elif args.command == "list-tokens":
            print(json.dumps(store.list_api_tokens(args.workspace_id, args.user_id), indent=2))
        elif args.command == "revoke-token":
            print(json.dumps({"revoked": store.revoke_api_token(args.workspace_id, args.user_id, args.token_id)}))
        elif args.command == "rotate-token":
            rotated = store.rotate_api_token(args.workspace_id, args.user_id, args.token_id)
            if rotated is None:
                raise SystemExit("token not found or not owned by user")
            print(json.dumps(rotated, indent=2))
        elif args.command == "token-policy":
            if args.default_expires_in_days is not None and args.clear_default_expiration:
                raise SystemExit("use --default-expires-in-days or --clear-default-expiration, not both")
            if args.rotation_due_in_days is not None and args.clear_rotation_due:
                raise SystemExit("use --rotation-due-in-days or --clear-rotation-due, not both")
            updates = {}
            if args.default_expires_in_days is not None:
                updates["default_expires_in_days"] = args.default_expires_in_days
            elif args.clear_default_expiration:
                updates["default_expires_in_days"] = None
            if args.rotation_due_in_days is not None:
                updates["rotation_due_in_days"] = args.rotation_due_in_days
            elif args.clear_rotation_due:
                updates["rotation_due_in_days"] = None
            if updates:
                policy = _workspace_member_cli(
                    lambda: store.set_api_token_policy(args.workspace_id, args.user_id, **updates)
                )
            else:
                policy = _workspace_member_cli(lambda: store.get_api_token_policy(args.workspace_id, args.user_id))
            print(json.dumps(policy, indent=2))
        elif args.command == "provider-config":
            has_updates = any(
                value is not None
                for value in (args.base_url, args.model, args.api_key_env_var, args.timeout_seconds)
            )
            if args.clear and has_updates:
                raise SystemExit("choose --clear or provider config fields")
            if sum(1 for selected in (args.clear, args.check, args.probe, has_updates) if selected) > 1:
                raise SystemExit("choose only one provider config action")
            if args.clear:
                config = _workspace_member_cli(
                    lambda: store.clear_workspace_provider_config(args.workspace_id, args.user_id)
                )
            elif args.check:
                config = _workspace_member_cli(
                    lambda: store.check_workspace_provider_config(args.workspace_id, args.user_id)
                )
            elif args.probe:
                config = _workspace_member_cli(
                    lambda: store.probe_workspace_provider_config(args.workspace_id, args.user_id)
                )
            elif has_updates:
                if args.base_url is None or args.model is None:
                    raise SystemExit("--base-url and --model are required when setting provider config")
                config = _workspace_member_cli(
                    lambda: store.set_workspace_provider_config(
                        args.workspace_id,
                        args.user_id,
                        base_url=args.base_url,
                        model=args.model,
                        api_key_env_var=args.api_key_env_var,
                        timeout_seconds=args.timeout_seconds,
                    )
                )
            else:
                config = _workspace_member_cli(
                    lambda: store.get_workspace_provider_config(args.workspace_id, args.user_id)
                )
            print(json.dumps(config, indent=2))
        elif args.command == "audit-sink":
            has_update = args.relative_path is not None or args.format is not None or args.disable
            selected_actions = [args.clear, args.check, args.status, has_update]
            if sum(1 for selected in selected_actions if selected) > 1:
                raise SystemExit("choose only one audit sink action")
            if args.clear:
                config = _workspace_member_cli(
                    lambda: store.clear_workspace_audit_jsonl_sink_config(args.workspace_id, args.user_id)
                )
            elif args.check:
                config = _workspace_member_cli(
                    lambda: store.check_workspace_audit_jsonl_sink(args.workspace_id, args.user_id)
                )
            elif args.status:
                config = _workspace_member_cli(
                    lambda: store.get_workspace_audit_jsonl_sink_status(args.workspace_id, args.user_id)
                )
            elif has_update:
                relative_path = args.relative_path
                audit_sink_format = args.format
                if (args.disable or audit_sink_format is not None) and relative_path is None:
                    current = _workspace_member_cli(
                        lambda: store.get_workspace_audit_jsonl_sink_config(args.workspace_id, args.user_id)
                    )
                    relative_path = current["relative_path"]
                    if audit_sink_format is None:
                        audit_sink_format = current["format"]
                    if not current["configured"] or relative_path is None:
                        raise SystemExit("--relative-path is required when updating an unconfigured audit sink")
                if relative_path is None:
                    raise SystemExit("--relative-path is required when setting audit sink")
                config = _workspace_member_cli(
                    lambda: store.set_workspace_audit_jsonl_sink_config(
                        args.workspace_id,
                        args.user_id,
                        relative_path=relative_path,
                        format=audit_sink_format,
                        enabled=not args.disable,
                    )
                )
            else:
                config = _workspace_member_cli(
                    lambda: store.get_workspace_audit_jsonl_sink_config(args.workspace_id, args.user_id)
                )
            print(json.dumps(config, indent=2))
        elif args.command == "workspace-export":
            manifest = _workspace_member_cli(
                lambda: store.export_workspace_bundle(args.workspace_id, args.user_id, args.output_path)
            )
            print(json.dumps(manifest, indent=2))
        elif args.command == "audit-log":
            events = store.list_audit_events(
                args.workspace_id,
                args.user_id,
                limit=args.limit,
                since=args.since,
                until=args.until,
                action=args.action,
                event_user_id=args.event_user_id,
                target_type=args.target_type,
                target_id=args.target_id,
            )
            print(
                json.dumps(
                    _redacted_audit_export_events(events),
                    indent=2,
                )
            )
        elif args.command == "audit-export":
            print(
                store.export_audit_events(
                    args.workspace_id,
                    args.user_id,
                    limit=args.limit,
                    since=args.since,
                    until=args.until,
                    action=args.action,
                    event_user_id=args.event_user_id,
                    target_type=args.target_type,
                    target_id=args.target_id,
                    format=args.format,
                ),
                end="",
            )
        elif args.command == "audit-integrity":
            report = _workspace_member_cli(lambda: store.verify_audit_integrity(args.workspace_id, args.user_id))
            print(json.dumps(report, indent=2))
        elif args.command == "audit-retention":
            if args.retention_days is not None and args.clear:
                raise SystemExit("choose --retention-days or --clear")
            if args.legal_hold and args.clear_legal_hold:
                raise SystemExit("choose --legal-hold or --clear-legal-hold")
            if args.clear_legal_hold and args.legal_hold_reason is not None:
                raise SystemExit("choose --clear-legal-hold or --legal-hold-reason")
            has_legal_hold_change = args.legal_hold or args.clear_legal_hold
            has_legal_hold_reason = args.legal_hold_reason is not None
            if args.retention_days is None and not args.clear and not has_legal_hold_change and not has_legal_hold_reason:
                policy = _workspace_member_cli(lambda: store.get_audit_retention_policy(args.workspace_id, args.user_id))
            else:
                policy = _workspace_member_cli(
                    lambda: store.set_audit_retention_policy(
                        args.workspace_id,
                        args.user_id,
                        retention_days=None if args.clear else (args.retention_days if args.retention_days is not None else _UNSET),
                        legal_hold=(True if args.legal_hold else False) if has_legal_hold_change else _UNSET,
                        legal_hold_reason=args.legal_hold_reason if has_legal_hold_reason else _UNSET,
                    )
                )
            print(json.dumps(policy, indent=2))
        elif args.command == "audit-purge":
            print(
                json.dumps(
                    _workspace_member_cli(
                        lambda: store.purge_audit_events_by_retention(args.workspace_id, args.user_id, dry_run=args.dry_run)
                    ),
                    indent=2,
                )
            )
        elif args.command == "query-retention":
            if args.retention_days is not None and args.clear:
                raise SystemExit("choose --retention-days or --clear")
            if args.legal_hold and args.clear_legal_hold:
                raise SystemExit("choose --legal-hold or --clear-legal-hold")
            if args.clear_legal_hold and args.legal_hold_reason is not None:
                raise SystemExit("choose --clear-legal-hold or --legal-hold-reason")
            has_legal_hold_change = args.legal_hold or args.clear_legal_hold
            has_legal_hold_reason = args.legal_hold_reason is not None
            if args.retention_days is None and not args.clear and not has_legal_hold_change and not has_legal_hold_reason:
                policy = _workspace_member_cli(lambda: store.get_query_retention_policy(args.workspace_id, args.user_id))
            else:
                policy = _workspace_member_cli(
                    lambda: store.set_query_retention_policy(
                        args.workspace_id,
                        args.user_id,
                        retention_days=None if args.clear else (args.retention_days if args.retention_days is not None else _UNSET),
                        legal_hold=(True if args.legal_hold else False) if has_legal_hold_change else _UNSET,
                        legal_hold_reason=args.legal_hold_reason if has_legal_hold_reason else _UNSET,
                    )
                )
            print(json.dumps(policy, indent=2))
        elif args.command == "query-purge":
            print(
                json.dumps(
                    _workspace_member_cli(
                        lambda: store.purge_query_runs_by_retention(args.workspace_id, args.user_id, dry_run=args.dry_run)
                    ),
                    indent=2,
                )
            )
        elif args.command == "query-export":
            print(
                _workspace_member_cli(
                    lambda: store.export_query_runs(
                        args.workspace_id,
                        args.user_id,
                        limit=args.limit,
                        run_actor_user_id=args.actor_user_id,
                        since=args.since,
                        until=args.until,
                        query=args.query,
                        format=args.format,
                    )
                ),
                end="",
            )
        elif args.command == "delete-query-run":
            print(
                json.dumps(
                    {
                        "deleted": _workspace_member_cli(
                            lambda: store.delete_query_run(
                                args.run_id,
                                workspace_id=args.workspace_id,
                                actor_user_id=args.user_id,
                            )
                        )
                    }
                )
            )
        elif args.command == "create-conversation":
            print(
                json.dumps(
                    _conversation_cli(
                        lambda: store.create_conversation(
                            args.workspace_id,
                            args.user_id,
                            title=args.title,
                            source_set_id=args.source_set_id,
                            folder_id=args.folder_id,
                        )
                    ),
                    indent=2,
                )
            )
        elif args.command == "list-conversations":
            print(
                json.dumps(
                    _conversation_cli(
                        lambda: store.list_conversations(
                            args.workspace_id,
                            args.user_id,
                            limit=args.limit,
                            include_archived=args.include_archived,
                        )
                    ),
                    indent=2,
                )
            )
        elif args.command == "archive-conversation":
            print(
                json.dumps(
                    _conversation_cli(
                        lambda: store.archive_conversation(
                            args.conversation_id,
                            args.user_id,
                            archived=not args.restore,
                        )
                    ),
                    indent=2,
                )
            )
        elif args.command == "rename-conversation":
            print(
                json.dumps(
                    _conversation_cli(
                        lambda: store.rename_conversation(args.conversation_id, args.user_id, args.title)
                    ),
                    indent=2,
                )
            )
        elif args.command == "set-conversation-scope":
            print(
                json.dumps(
                    _conversation_cli(
                        lambda: store.update_conversation_scope(
                            args.conversation_id,
                            args.user_id,
                            source_set_id=args.source_set_id,
                            folder_id=args.folder_id,
                            clear_scope=args.clear,
                        )
                    ),
                    indent=2,
                )
            )
        elif args.command == "delete-conversation":
            print(
                json.dumps(
                    {
                        "deleted": _conversation_cli(
                            lambda: store.delete_conversation(args.conversation_id, args.user_id)
                        )
                    },
                    indent=2,
                )
            )
        elif args.command == "conversation-messages":
            print(
                json.dumps(
                    _conversation_cli(
                        lambda: store.list_conversation_messages(
                            args.conversation_id,
                            args.user_id,
                            limit=args.limit,
                        )
                    ),
                    indent=2,
                )
            )
        elif args.command == "export-conversation":
            print(
                _conversation_cli(
                    lambda: store.export_conversation_transcript(
                        args.conversation_id,
                        args.user_id,
                        limit=args.limit,
                        format=args.format,
                    )
                ),
                end="",
            )
        elif args.command == "conversation-share":
            selected_actions = [
                bool(args.share),
                bool(args.shares),
                bool(args.revoke_share),
            ]
            if sum(selected_actions) != 1:
                raise SystemExit("choose --share, --shares, or --revoke-share")
            share_option_used = (
                args.share_redact
                or args.share_expires_at is not None
                or args.share_expires_in_days is not None
                or args.share_max_views is not None
                or args.share_password is not None
            )
            if share_option_used and not args.share:
                raise SystemExit("share options require --share")
            if args.share_expires_at is not None and args.share_expires_in_days is not None:
                raise SystemExit("use --share-expires-at or --share-expires-in-days, not both")
            if args.share:
                expires_at = args.share_expires_at
                if args.share_expires_in_days is not None:
                    expires_at = expires_at_from_days(args.share_expires_in_days)
                share_link = _conversation_cli(
                    lambda: store.create_conversation_share_link(
                        args.share,
                        args.user_id,
                        expected_workspace_id=args.workspace_id,
                        expires_at=expires_at,
                        redact_content=args.share_redact,
                        max_views=args.share_max_views,
                        password=args.share_password,
                    )
                )
                print(json.dumps(share_link, indent=2))
            elif args.shares:
                print(
                    json.dumps(
                        _conversation_cli(
                            lambda: store.list_conversation_share_links(
                                args.shares,
                                args.user_id,
                                expected_workspace_id=args.workspace_id,
                            )
                        ),
                        indent=2,
                    )
                )
            else:
                revoked = _conversation_cli(
                    lambda: store.revoke_conversation_share_link(
                        args.revoke_share,
                        args.user_id,
                        expected_workspace_id=args.workspace_id,
                    )
                )
                print(json.dumps({"revoked": revoked}, indent=2))
        elif args.command == "chat-message":
            print(
                json.dumps(
                    _conversation_cli(
                        lambda: store.chat_message(
                            args.conversation_id,
                            args.user_id,
                            args.message,
                            doc_ids=args.doc_ids,
                            expert_hints=args.expert_hints,
                            limit=args.limit,
                        )
                    ),
                    indent=2,
                )
            )
        elif args.command == "register-doc":
            print(
                store.register_document(
                    name=args.name,
                    source_path=args.source_path,
                    kind=args.kind,
                    description=args.description,
                    folder_id=args.folder_id,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
                    page_count=args.page_count,
                )
            )
        elif args.command == "delete-doc":
            print(
                json.dumps(
                    {
                        "deleted": _delete_document_cli(
                            lambda: store.delete_document(
                                args.doc_id,
                                workspace_id=args.workspace_id,
                                actor_user_id=args.user_id,
                            )
                        )
                    }
                )
            )
        elif args.command == "rename-doc":
            document = _reindex_document_cli(
                lambda: store.rename_document(
                    args.doc_id,
                    args.name,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
                )
            )
            print(json.dumps({"updated": True, "document": document}, indent=2))
        elif args.command == "move-doc":
            if args.folder_id and args.clear_folder:
                raise SystemExit("choose --folder-id or --clear-folder")
            if not args.folder_id and not args.clear_folder:
                raise SystemExit("choose --folder-id or --clear-folder")
            document = _reindex_document_cli(
                lambda: store.move_document(
                    args.doc_id,
                    None if args.clear_folder else args.folder_id,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
                )
            )
            print(json.dumps({"updated": True, "document": document}, indent=2))
        elif args.command == "reindex-doc":
            document = _reindex_document_cli(
                lambda: store.reindex_document_file(
                    args.doc_id,
                    args.path,
                    name=args.name,
                    folder_id=args.folder_id,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
                )
            )
            print(json.dumps({"updated": True, "document": document}, indent=2))
        elif args.command == "document-versions":
            print(
                json.dumps(
                    _workspace_member_cli(
                        lambda: store.list_document_versions(
                            args.doc_id,
                            workspace_id=args.workspace_id,
                            actor_user_id=args.user_id,
                            limit=args.limit,
                        )
                    ),
                    indent=2,
                )
            )
        elif args.command == "document-access":
            actions = [
                args.mode is not None,
                args.grant_user is not None,
                args.revoke_user is not None,
                args.grant_group is not None,
                args.revoke_group is not None,
            ]
            if sum(actions) > 1:
                raise SystemExit("choose only one document access action")
            if args.mode is not None:
                access = _workspace_member_cli(
                    lambda: store.set_document_access_mode(
                        args.doc_id,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.actor_user_id,
                        access_mode=args.mode,
                    )
                )
            elif args.grant_user is not None:
                access = _workspace_member_cli(
                    lambda: store.grant_document_access(
                        args.doc_id,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.actor_user_id,
                        user_id=args.grant_user,
                        role=args.role,
                    )
                )
            elif args.grant_group is not None:
                access = _workspace_member_cli(
                    lambda: store.grant_document_group_access(
                        args.doc_id,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.actor_user_id,
                        group_id=args.grant_group,
                        role=args.role,
                    )
                )
            elif args.revoke_user is not None:
                access = {
                    "revoked": _workspace_member_cli(
                        lambda: store.revoke_document_access(
                            args.doc_id,
                            workspace_id=args.workspace_id,
                            actor_user_id=args.actor_user_id,
                            user_id=args.revoke_user,
                        )
                    )
                }
            elif args.revoke_group is not None:
                access = {
                    "revoked": _workspace_member_cli(
                        lambda: store.revoke_document_group_access(
                            args.doc_id,
                            workspace_id=args.workspace_id,
                            actor_user_id=args.actor_user_id,
                            group_id=args.revoke_group,
                        )
                    )
                }
            else:
                access = _workspace_member_cli(
                    lambda: store.list_document_access(
                        args.doc_id,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.actor_user_id,
                    )
                )
            if access is None:
                raise SystemExit("document not found")
            print(json.dumps(access, indent=2))
        elif args.command == "acl-bulk":
            try:
                with open(args.policy_path, encoding="utf-8") as handle:
                    policy = json.load(handle)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"invalid ACL policy JSON: {exc}") from exc
            report = _workspace_member_cli(
                lambda: store.apply_acl_bulk(
                    args.workspace_id,
                    args.actor_user_id,
                    policy,
                    dry_run=not args.apply,
                )
            )
            print(json.dumps(report, indent=2))
        elif args.command == "document-share":
            selected_actions = [
                bool(args.share),
                bool(args.shares),
                bool(args.revoke_share),
            ]
            if sum(selected_actions) != 1:
                raise SystemExit("choose --share, --shares, or --revoke-share")
            share_option_used = (
                args.share_redact
                or args.share_expires_at is not None
                or args.share_expires_in_days is not None
                or args.share_max_views is not None
                or args.share_password is not None
            )
            if share_option_used and not args.share:
                raise SystemExit("share options require --share")
            if args.share_expires_at is not None and args.share_expires_in_days is not None:
                raise SystemExit("use --share-expires-at or --share-expires-in-days, not both")
            if args.share:
                expires_at = args.share_expires_at
                if args.share_expires_in_days is not None:
                    expires_at = expires_at_from_days(args.share_expires_in_days)
                share_link = _workspace_member_cli(
                    lambda: store.create_document_share_link(
                        args.share,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.user_id,
                        expires_at=expires_at,
                        redact_content=args.share_redact,
                        max_views=args.share_max_views,
                        password=args.share_password,
                    )
                )
                if share_link is None:
                    raise SystemExit("document not found")
                print(json.dumps(share_link, indent=2))
            elif args.shares:
                print(
                    json.dumps(
                        _workspace_member_cli(
                            lambda: store.list_document_share_links(
                                args.shares,
                                workspace_id=args.workspace_id,
                                actor_user_id=args.user_id,
                            )
                        ),
                        indent=2,
                    )
                )
            else:
                revoked = _workspace_member_cli(
                    lambda: store.revoke_document_share_link(
                        args.revoke_share,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.user_id,
                    )
                )
                print(json.dumps({"revoked": revoked}, indent=2))
        elif args.command == "ingest-file":
            print(
                _workspace_member_cli(
                    lambda: store.ingest_file(
                        args.path,
                        folder_id=args.folder_id,
                        name=args.name,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.user_id,
                    )
                )
            )
        elif args.command == "import-structure":
            print(
                _workspace_member_cli(
                    lambda: store.import_pageindex_structure(
                        args.path,
                        doc_id=args.doc_id,
                        folder_id=args.folder_id,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.user_id,
                    )
                )
            )
        elif args.command == "search":
            print(
                json.dumps(
                    store.search_documents(
                        args.query,
                        args.limit,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.user_id,
                    ),
                    indent=2,
                )
            )
        elif args.command == "query":
            selected_scopes = [bool(args.doc_ids), bool(args.source_set_id), bool(args.folder_id)]
            if sum(selected_scopes) > 1:
                if args.doc_ids and args.source_set_id and not args.folder_id:
                    raise SystemExit("use --doc-id or --source-set-id, not both")
                raise SystemExit("use only one of --doc-id, --source-set-id, or --folder-id")
            print(
                json.dumps(
                    store.query_corpus(
                        args.query,
                        doc_ids=args.doc_ids,
                        source_set_id=args.source_set_id,
                        folder_id=args.folder_id,
                        expert_hints=args.expert_hints,
                        workspace_id=args.workspace_id,
                        limit=args.limit,
                        actor_user_id=args.user_id,
                    ),
                    indent=2,
                )
            )
        elif args.command == "query-source-set":
            selected_actions = [
                bool(args.create),
                bool(args.update),
                bool(args.delete),
                bool(args.share),
                bool(args.shares),
                bool(args.revoke_share),
            ]
            if sum(selected_actions) > 1:
                raise SystemExit("use only one query-source-set action")
            if args.shared and args.private:
                raise SystemExit("use --shared or --private, not both")
            source_set_option_used = (
                args.name is not None
                or args.description is not None
                or args.doc_ids is not None
                or args.shared
                or args.private
            )
            if source_set_option_used and not (args.create or args.update):
                raise SystemExit("source set options require --create or --update")
            share_option_used = (
                args.share_redact
                or args.share_expires_at is not None
                or args.share_expires_in_days is not None
                or args.share_max_views is not None
                or args.share_password is not None
            )
            if share_option_used and not args.share:
                raise SystemExit("share options require --share")
            if args.share_expires_at is not None and args.share_expires_in_days is not None:
                raise SystemExit("use --share-expires-at or --share-expires-in-days, not both")
            if args.delete:
                deleted = _workspace_member_cli(
                    lambda: store.delete_query_source_set(args.workspace_id, args.user_id, args.delete)
                )
                print(json.dumps({"deleted": deleted}, indent=2))
            elif args.update:
                if args.name is None and args.description is None and args.doc_ids is None and not args.shared and not args.private:
                    raise SystemExit("use --name, --description, --doc-id, --shared, or --private with --update")
                source_set = _workspace_member_cli(
                    lambda: store.update_query_source_set(
                        args.workspace_id,
                        args.user_id,
                        args.update,
                        name=args.name if args.name is not None else _UNSET,
                        description=args.description if args.description is not None else _UNSET,
                        doc_ids=args.doc_ids if args.doc_ids is not None else _UNSET,
                        shared=True if args.shared else False if args.private else _UNSET,
                    )
                )
                print(json.dumps(source_set, indent=2))
            elif args.create:
                source_set = _workspace_member_cli(
                    lambda: store.create_query_source_set(
                        args.workspace_id,
                        args.user_id,
                        args.create,
                        args.doc_ids,
                        description=args.description,
                        shared=args.shared,
                    )
                )
                print(json.dumps(source_set, indent=2))
            elif args.share:
                expires_at = args.share_expires_at
                if args.share_expires_in_days is not None:
                    expires_at = expires_at_from_days(args.share_expires_in_days)
                share_link = _workspace_member_cli(
                    lambda: store.create_query_source_set_share_link(
                        args.workspace_id,
                        args.user_id,
                        args.share,
                        expires_at=expires_at,
                        redact_content=args.share_redact,
                        max_views=args.share_max_views,
                        password=args.share_password,
                    )
                )
                if share_link is None:
                    raise SystemExit("source set not found")
                print(json.dumps(share_link, indent=2))
            elif args.shares:
                print(
                    json.dumps(
                        _workspace_member_cli(
                            lambda: store.list_query_source_set_share_links(
                                args.workspace_id,
                                args.user_id,
                                args.shares,
                            )
                        ),
                        indent=2,
                    )
                )
            elif args.revoke_share:
                revoked = _workspace_member_cli(
                    lambda: store.revoke_query_source_set_share_link(
                        args.workspace_id,
                        args.user_id,
                        args.revoke_share,
                    )
                )
                print(json.dumps({"revoked": revoked}, indent=2))
            else:
                print(
                    json.dumps(
                        _workspace_member_cli(
                            lambda: store.list_query_source_sets(args.workspace_id, args.user_id)
                        ),
                        indent=2,
                    )
                )
        elif args.command == "query-tree":
            print(
                json.dumps(
                    store.build_query_tree(
                        args.query,
                        doc_ids=args.doc_ids,
                        expert_hints=args.expert_hints,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.user_id,
                        limit=args.limit,
                    ),
                    indent=2,
                )
            )
        elif args.command == "hybrid-search":
            print(
                json.dumps(
                    store.hybrid_search(
                        args.query,
                        doc_ids=args.doc_ids,
                        expert_hints=args.expert_hints,
                        workspace_id=args.workspace_id,
                        actor_user_id=args.user_id,
                        limit=args.limit,
                    ),
                    indent=2,
                )
            )
        elif args.command == "verify-trace":
            print(json.dumps(store.verify_trace(args.run_id), indent=2))
        elif args.command == "rebuild-virtual-index":
            store.rebuild_virtual_index()
            print(json.dumps(store.list_virtual_nodes(), indent=2))
        elif args.command == "virtual-nodes":
            if args.query:
                print(json.dumps(store.plan_query_tree(args.query, workspace_id=args.workspace_id), indent=2))
            else:
                print(json.dumps(store.list_virtual_nodes(workspace_id=args.workspace_id), indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
