from __future__ import annotations

import argparse
import json

from .deployment import run_deployment_check
from .eval import run_enterprise_eval
from .server import serve
from .store import API_TOKEN_SCOPES, EnterpriseStore, expires_at_from_days


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

    remove_member = sub.add_parser("remove-member")
    remove_member.add_argument("workspace_id")
    remove_member.add_argument("user_id")
    remove_member.add_argument("actor_user_id")

    invite_member = sub.add_parser("invite-member")
    invite_member.add_argument("workspace_id")
    invite_member.add_argument("actor_user_id")
    invite_member.add_argument("email")
    invite_member.add_argument("--role", default="member")
    invite_member.add_argument("--expires-in-days", type=_positive_int)

    list_invitations = sub.add_parser("list-invitations")
    list_invitations.add_argument("workspace_id")
    list_invitations.add_argument("actor_user_id")
    list_invitations.add_argument("--status", choices=["pending", "accepted", "revoked"])

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

    workspace_export = sub.add_parser("workspace-export")
    workspace_export.add_argument("workspace_id")
    workspace_export.add_argument("user_id")
    workspace_export.add_argument("output_path")

    audit_log = sub.add_parser("audit-log")
    audit_log.add_argument("workspace_id")
    audit_log.add_argument("user_id")
    audit_log.add_argument("--limit", type=int, default=100)
    audit_log.add_argument("--since")
    audit_log.add_argument("--until")
    audit_log.add_argument("--action")

    audit_export = sub.add_parser("audit-export")
    audit_export.add_argument("workspace_id")
    audit_export.add_argument("user_id")
    audit_export.add_argument("--limit", type=int, default=500)
    audit_export.add_argument("--since")
    audit_export.add_argument("--until")
    audit_export.add_argument("--action")
    audit_export.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")

    audit_retention = sub.add_parser("audit-retention")
    audit_retention.add_argument("workspace_id")
    audit_retention.add_argument("user_id")
    audit_retention.add_argument("--retention-days", type=_positive_int)
    audit_retention.add_argument("--clear", action="store_true")

    audit_purge = sub.add_parser("audit-purge")
    audit_purge.add_argument("workspace_id")
    audit_purge.add_argument("user_id")
    audit_purge.add_argument("--dry-run", action="store_true")

    create_conversation = sub.add_parser("create-conversation")
    create_conversation.add_argument("workspace_id")
    create_conversation.add_argument("user_id")
    create_conversation.add_argument("--title")

    list_conversations = sub.add_parser("list-conversations")
    list_conversations.add_argument("workspace_id")
    list_conversations.add_argument("user_id")
    list_conversations.add_argument("--limit", type=int, default=50)

    conversation_messages = sub.add_parser("conversation-messages")
    conversation_messages.add_argument("conversation_id")
    conversation_messages.add_argument("user_id")
    conversation_messages.add_argument("--limit", type=int, default=100)

    export_conversation = sub.add_parser("export-conversation")
    export_conversation.add_argument("conversation_id")
    export_conversation.add_argument("user_id")
    export_conversation.add_argument("--limit", type=int, default=500)
    export_conversation.add_argument("--format", choices=["jsonl", "markdown"], default="jsonl")

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
    query.add_argument("--hint", action="append", dest="expert_hints")
    query.add_argument("--workspace-id")
    query.add_argument("--user-id")
    query.add_argument("--limit", type=int, default=8)

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

    eval_cmd = sub.add_parser("eval")
    eval_cmd.add_argument("--fixtures-root")

    deployment_check = sub.add_parser("deployment-check")
    deployment_check.add_argument("--require-api-token", action="store_true")
    deployment_check.add_argument("--check-provider", action="store_true")
    deployment_check.add_argument("--require-provider-api-key", action="store_true")

    args = parser.parse_args()
    if args.command == "serve":
        serve(args.root, host=args.host, port=args.port, require_api_token=args.require_api_token)
        return
    if args.command == "eval":
        print(json.dumps(run_enterprise_eval(args.root, fixtures_root=args.fixtures_root), indent=2))
        return
    if args.command == "deployment-check":
        print(
            json.dumps(
                run_deployment_check(
                    args.root,
                    require_api_token=args.require_api_token,
                    check_provider=args.check_provider,
                    require_provider_api_key=args.require_provider_api_key,
                ),
                indent=2,
            )
        )
        return

    store = EnterpriseStore(args.root)
    try:
        if args.command == "folder":
            print(store.create_folder(args.name, args.parent_id, workspace_id=args.workspace_id, actor_user_id=args.user_id))
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
            if args.clear:
                config = _workspace_member_cli(
                    lambda: store.clear_workspace_provider_config(args.workspace_id, args.user_id)
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
        elif args.command == "workspace-export":
            manifest = _workspace_member_cli(
                lambda: store.export_workspace_bundle(args.workspace_id, args.user_id, args.output_path)
            )
            print(json.dumps(manifest, indent=2))
        elif args.command == "audit-log":
            print(
                json.dumps(
                    store.list_audit_events(
                        args.workspace_id,
                        args.user_id,
                        limit=args.limit,
                        since=args.since,
                        until=args.until,
                        action=args.action,
                    ),
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
                    format=args.format,
                ),
                end="",
            )
        elif args.command == "audit-retention":
            if args.retention_days is not None and args.clear:
                raise SystemExit("choose --retention-days or --clear")
            if args.retention_days is None and not args.clear:
                policy = _workspace_member_cli(lambda: store.get_audit_retention_policy(args.workspace_id, args.user_id))
            else:
                policy = _workspace_member_cli(
                    lambda: store.set_audit_retention_policy(
                        args.workspace_id,
                        args.user_id,
                        retention_days=None if args.clear else args.retention_days,
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
        elif args.command == "create-conversation":
            print(
                json.dumps(
                    _conversation_cli(
                        lambda: store.create_conversation(args.workspace_id, args.user_id, title=args.title)
                    ),
                    indent=2,
                )
            )
        elif args.command == "list-conversations":
            print(
                json.dumps(
                    _conversation_cli(lambda: store.list_conversations(args.workspace_id, args.user_id, limit=args.limit)),
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
            actions = [args.mode is not None, args.grant_user is not None, args.revoke_user is not None]
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
        elif args.command == "ingest-file":
            print(
                store.ingest_file(
                    args.path,
                    folder_id=args.folder_id,
                    name=args.name,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
                )
            )
        elif args.command == "import-structure":
            print(
                store.import_pageindex_structure(
                    args.path,
                    doc_id=args.doc_id,
                    folder_id=args.folder_id,
                    workspace_id=args.workspace_id,
                    actor_user_id=args.user_id,
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
            print(
                json.dumps(
                    store.query_corpus(
                        args.query,
                        doc_ids=args.doc_ids,
                        expert_hints=args.expert_hints,
                        workspace_id=args.workspace_id,
                        limit=args.limit,
                        actor_user_id=args.user_id,
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
