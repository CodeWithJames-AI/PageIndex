from __future__ import annotations


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PageIndex</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1f2933;
      --muted: #667085;
      --line: #d8dee8;
      --panel: #f7f9fc;
      --field: #ffffff;
      --accent: #2663eb;
      --accent-strong: #1749b8;
      --good: #0f7b5f;
      --warn: #a15c07;
      --danger: #b42318;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: #eef2f7;
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button,
    input,
    select,
    textarea {
      font: inherit;
    }
    button {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #ffffff;
      min-height: 36px;
      padding: 0 12px;
      border-radius: 6px;
      cursor: pointer;
    }
    button:hover {
      background: var(--accent-strong);
      border-color: var(--accent-strong);
    }
    button.secondary {
      background: #ffffff;
      color: var(--accent);
    }
    input,
    select,
    textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--field);
      color: var(--ink);
      padding: 9px 10px;
      min-height: 36px;
    }
    textarea {
      min-height: 96px;
      resize: vertical;
    }
    label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }
    pre {
      margin: 0;
      overflow: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .app {
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 100vh;
    }
    .topbar {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 18px;
      align-items: center;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
      padding: 14px 18px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 150px;
      font-size: 18px;
      font-weight: 750;
    }
    .mark {
      display: inline-grid;
      place-items: center;
      width: 28px;
      height: 28px;
      border-radius: 6px;
      background: #22314a;
      color: #ffffff;
      font-size: 14px;
    }
    .identity {
      display: grid;
      grid-template-columns: minmax(160px, 1fr) minmax(120px, 180px) minmax(180px, 1fr) auto;
      gap: 10px;
      align-items: end;
    }
    .workspace {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      min-height: 0;
    }
    .sidebar {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 16px;
      overflow: auto;
    }
    .main {
      display: grid;
      grid-template-rows: auto 1fr;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
    }
    .querybar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(150px, 220px) 110px;
      gap: 10px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
      padding: 16px;
    }
    .content {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
      gap: 0;
      min-height: 0;
      overflow: hidden;
    }
    .answer,
    .trace {
      padding: 16px;
      overflow: auto;
    }
    .answer {
      background: #ffffff;
    }
    .trace {
      border-left: 1px solid var(--line);
      background: #fbfcfe;
    }
    .section-title {
      margin: 0 0 12px;
      font-size: 13px;
      color: var(--muted);
      font-weight: 750;
      text-transform: uppercase;
    }
    .stack {
      display: grid;
      gap: 12px;
    }
    .import-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 82px;
      gap: 8px;
    }
    .doc-list,
    .folder-list,
    .virtual-node-list,
    .citations,
    .conversation-list,
    .query-run-list,
    .member-list,
    .group-list,
    .token-list,
    .audit-list,
    .version-list,
    .page-list,
    .message-list {
      display: grid;
      gap: 8px;
    }
    .doc,
    .folder,
    .virtual-node,
    .citation,
    .conversation,
    .query-run,
    .member,
    .token,
    .audit-event,
    .version,
    .page-preview,
    .message {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      padding: 10px;
    }
    .conversation {
      text-align: left;
      color: var(--ink);
      border-color: var(--line);
      min-height: auto;
    }
    .conversation.active {
      border-color: var(--accent);
      box-shadow: inset 3px 0 0 var(--accent);
    }
    .folder.active {
      border-color: var(--accent);
      box-shadow: inset 3px 0 0 var(--accent);
    }
    .message.user {
      border-color: #b9c7e8;
      background: #f6f8ff;
    }
    .message.assistant {
      border-color: #bfd7ce;
      background: #f5fbf8;
    }
    .chat-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 86px;
      gap: 8px;
      align-items: end;
    }
    .member-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 84px;
      gap: 8px;
      align-items: center;
    }
    .doc-actions {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      margin-top: 8px;
    }
    .conversation .doc-actions {
      grid-template-columns: 1fr;
    }
    .access-actions {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
      margin-top: 8px;
    }
    .token-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 8px;
    }
    .scope-row {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }
    .scope-row label {
      display: flex;
      gap: 6px;
      align-items: center;
      font-size: 12px;
      color: var(--ink);
    }
    .scope-row input {
      width: auto;
      min-height: auto;
    }
    .provider-actions {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
    }
    .download-link {
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }
    .download-link[hidden] {
      display: none;
    }
    .doc strong,
    .citation strong {
      display: block;
      margin-bottom: 4px;
    }
    .muted {
      color: var(--muted);
    }
    .status {
      min-height: 20px;
      color: var(--muted);
    }
    .status.ok {
      color: var(--good);
    }
    .status.warn {
      color: var(--warn);
    }
    .status.error {
      color: var(--danger);
    }
    @media (max-width: 860px) {
      .topbar,
      .identity,
      .workspace,
      .content,
      .querybar {
        grid-template-columns: 1fr;
      }
      .sidebar,
      .trace {
        border: 0;
        border-top: 1px solid var(--line);
      }
      .workspace,
      .content {
        overflow: visible;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header class="topbar">
      <div class="brand"><span class="mark">PI</span><span>PageIndex</span></div>
      <div class="identity">
        <label>Workspace
          <input id="workspaceInput" value="" placeholder="workspace id">
        </label>
        <label>User
          <input id="userInput" value="alice" placeholder="user id">
        </label>
        <label>API token
          <input id="apiTokenInput" type="password" value="" placeholder="Bearer token">
        </label>
        <button id="refreshButton" class="secondary" type="button">Refresh</button>
      </div>
    </header>
    <div class="workspace">
      <aside class="sidebar">
        <div class="stack">
          <section>
            <h2 class="section-title">Folders</h2>
            <div class="stack">
              <div class="import-row">
                <input id="folderNameInput" value="" placeholder="folder name" aria-label="Folder name">
                <button id="createFolderButton" type="button">Create</button>
              </div>
              <select id="folderSelect" aria-label="Target folder">
                <option value="">No folder</option>
              </select>
              <button id="refreshFoldersButton" class="secondary" type="button">Refresh folders</button>
              <div id="folderList" class="folder-list muted">No folders loaded.</div>
              <button id="loadFolderAccessButton" class="secondary" type="button">Folder access</button>
              <div class="access-actions">
                <input id="folderAccessUserInput" value="" placeholder="user id" aria-label="Folder access user id">
                <button id="grantFolderAccessButton" type="button">Grant user</button>
                <button id="revokeFolderAccessButton" class="secondary" type="button">Revoke user</button>
              </div>
              <div class="access-actions">
                <input id="folderAccessGroupInput" value="" placeholder="group id" aria-label="Folder access group id">
                <button id="grantFolderGroupAccessButton" type="button">Grant group</button>
                <button id="revokeFolderGroupAccessButton" class="secondary" type="button">Revoke group</button>
              </div>
              <div id="folderAccessPanel" class="muted">No folder access loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Virtual nodes</h2>
            <div class="stack">
              <input id="virtualNodeQueryInput" value="" placeholder="plan query" aria-label="Virtual-node plan query">
              <div class="provider-actions">
                <button id="refreshVirtualNodesButton" class="secondary" type="button">Refresh</button>
                <button id="planVirtualNodesButton" type="button">Plan</button>
                <span></span>
              </div>
              <div id="virtualNodeList" class="virtual-node-list muted">No virtual nodes loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Upload</h2>
            <div class="import-row">
              <input id="uploadInput" type="file" aria-label="Upload files" multiple>
              <button id="uploadButton" type="button">Upload</button>
            </div>
          </section>
          <section>
            <h2 class="section-title">Server path</h2>
            <div class="stack">
              <input id="fileInput" value="" placeholder="absolute file path" aria-label="File path">
              <div class="import-row">
                <input id="fileNameInput" value="" placeholder="display name" aria-label="File display name">
                <button id="ingestButton" type="button">Ingest</button>
              </div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Structure</h2>
            <div class="import-row">
              <input id="structureInput" value="" placeholder="absolute structure JSON path" aria-label="Structure path">
              <button id="importButton" type="button">Import</button>
            </div>
          </section>
          <section>
            <h2 class="section-title">Conversations</h2>
            <div class="stack">
              <div class="import-row">
                <input id="conversationTitleInput" value="" placeholder="conversation title" aria-label="Conversation title">
                <button id="createConversationButton" type="button">New</button>
              </div>
              <div class="import-row">
                <select id="conversationExportFormatInput" aria-label="Conversation export format">
                  <option value="jsonl">jsonl</option>
                  <option value="markdown">markdown</option>
                </select>
                <button id="exportConversationButton" class="secondary" type="button">Export</button>
              </div>
              <div class="provider-actions">
                <button id="refreshConversationsButton" class="secondary" type="button">Refresh chats</button>
                <label class="checkbox-row"><input id="conversationIncludeArchivedInput" type="checkbox"> Archived</label>
              </div>
              <div id="conversationList" class="conversation-list muted">No conversations loaded.</div>
              <textarea id="conversationExportText" readonly placeholder="conversation export output" aria-label="Conversation export output"></textarea>
              <div id="conversationShareList" class="member-list muted">No conversation shares loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Members</h2>
            <div class="stack">
              <input id="memberUserInput" value="" placeholder="user id" aria-label="Member user id">
              <div class="import-row">
                <select id="memberRoleInput" aria-label="Member role">
                  <option value="viewer">viewer</option>
                  <option value="member" selected>member</option>
                  <option value="admin">admin</option>
                  <option value="owner">owner</option>
                </select>
                <button id="saveMemberButton" type="button">Save</button>
              </div>
              <button id="refreshMembersButton" class="secondary" type="button">Refresh team</button>
              <div id="memberList" class="member-list muted">No members loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Groups</h2>
            <div class="stack">
              <div class="import-row">
                <input id="groupNameInput" value="" placeholder="group name" aria-label="Group name">
                <button id="createGroupButton" type="button">Create</button>
              </div>
              <input id="groupMemberUserInput" value="" placeholder="member user id" aria-label="Group member user id">
              <button id="refreshGroupsButton" class="secondary" type="button">Refresh groups</button>
              <div id="groupList" class="group-list muted">No groups loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Usage</h2>
            <div class="stack">
              <button id="refreshUsageButton" class="secondary" type="button">Refresh usage</button>
              <div id="usageSummary" class="muted">Usage not loaded.</div>
              <pre id="usageReportText">{}</pre>
            </div>
          </section>
          <section>
            <h2 class="section-title">Quotas</h2>
            <div class="stack">
              <input id="quotaDocumentsInput" value="" placeholder="max documents" aria-label="Maximum documents">
              <input id="quotaPagesInput" value="" placeholder="max pages" aria-label="Maximum pages">
              <input id="quotaMembersInput" value="" placeholder="max members" aria-label="Maximum members">
              <div class="provider-actions">
                <button id="refreshQuotaPolicyButton" class="secondary" type="button">Policy</button>
                <button id="saveQuotaPolicyButton" type="button">Save</button>
                <button id="clearQuotaPolicyButton" class="secondary" type="button">Clear</button>
              </div>
              <div id="quotaPolicySummary" class="muted">Quota not loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Invitations</h2>
            <div class="stack">
              <input id="invitationEmailInput" value="" placeholder="email" aria-label="Invitation email">
              <input id="invitationExpiresInDaysInput" value="" placeholder="expires in days" aria-label="Invitation expiration days">
              <div class="import-row">
                <select id="invitationRoleInput" aria-label="Invitation role">
                  <option value="viewer">viewer</option>
                  <option value="member" selected>member</option>
                  <option value="admin">admin</option>
                </select>
                <button id="createInvitationButton" type="button">Invite</button>
              </div>
              <button id="refreshInvitationsButton" class="secondary" type="button">Refresh invites</button>
              <div id="invitationList" class="member-list muted">No invitations loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Tokens</h2>
            <div class="stack">
              <input id="tokenNameInput" value="" placeholder="token name" aria-label="API token name">
              <input id="tokenExpiresInDaysInput" value="" placeholder="expires in days" aria-label="API token expiration days">
              <div class="scope-row" aria-label="API token scopes">
                <label><input id="tokenScopeReadInput" type="checkbox" checked>read</label>
                <label><input id="tokenScopeWriteInput" type="checkbox" checked>write</label>
                <label><input id="tokenScopeAuditInput" type="checkbox" checked>audit</label>
              </div>
              <div class="token-actions">
                <button id="refreshTokensButton" class="secondary" type="button">Refresh</button>
                <button id="createTokenButton" type="button">Create</button>
              </div>
              <input id="tokenSecretOutput" readonly value="" placeholder="one-time token secret" aria-label="One-time API token secret">
              <div id="tokenList" class="token-list muted">No tokens loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Token policy</h2>
            <div class="stack">
              <input id="tokenPolicyDefaultExpirationInput" value="" placeholder="default expiration days" aria-label="Default API token expiration days">
              <input id="tokenPolicyRotationDueInput" value="" placeholder="rotation due days" aria-label="API token rotation due days">
              <div class="provider-actions">
                <button id="refreshTokenPolicyButton" class="secondary" type="button">Policy</button>
                <button id="saveTokenPolicyButton" type="button">Save</button>
                <button id="clearTokenPolicyButton" class="secondary" type="button">Clear</button>
              </div>
              <div id="tokenPolicySummary" class="muted">Policy not loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Audit</h2>
            <div class="stack">
              <input id="auditActionInput" value="" placeholder="action filter" aria-label="Audit action filter">
              <input id="auditUserFilterInput" value="" placeholder="actor user id" aria-label="Audit user filter">
              <div class="import-row">
                <input id="auditTargetTypeInput" value="" placeholder="target type" aria-label="Audit target type filter">
                <input id="auditTargetIdInput" value="" placeholder="target id" aria-label="Audit target id filter">
              </div>
              <div class="import-row">
                <select id="auditFormatInput" aria-label="Audit export format">
                  <option value="jsonl">jsonl</option>
                  <option value="csv">csv</option>
                </select>
                <button id="refreshAuditButton" class="secondary" type="button">Refresh</button>
              </div>
              <button id="exportAuditButton" class="secondary" type="button">Export audit</button>
              <button id="verifyAuditIntegrityButton" class="secondary" type="button">Verify ledger</button>
              <div class="import-row">
                <input id="auditRetentionDaysInput" value="" placeholder="retention days" aria-label="Audit retention days">
                <button id="saveAuditRetentionButton" type="button">Save</button>
              </div>
              <div class="provider-actions">
                <button id="refreshAuditRetentionButton" class="secondary" type="button">Policy</button>
                <button id="previewAuditPurgeButton" class="secondary" type="button">Preview</button>
                <button id="purgeAuditButton" class="secondary" type="button">Purge</button>
              </div>
              <div class="provider-actions">
                <button id="enableAuditLegalHoldButton" class="secondary" type="button">Hold</button>
                <button id="clearAuditLegalHoldButton" class="secondary" type="button">Release</button>
              </div>
              <input id="auditLegalHoldReasonInput" value="" placeholder="legal hold reason" aria-label="Audit legal hold reason">
              <button id="clearAuditRetentionButton" class="secondary" type="button">Clear retention</button>
              <div id="auditRetentionSummary" class="muted">Retention not loaded.</div>
              <div id="auditIntegritySummary" class="muted">Integrity not checked.</div>
              <pre id="auditIntegrityReportText">{}</pre>
              <div id="auditList" class="audit-list muted">No audit events loaded.</div>
              <textarea id="auditExportText" readonly placeholder="audit export output" aria-label="Audit export output"></textarea>
            </div>
          </section>
          <section>
            <h2 class="section-title">Workspace export</h2>
            <div class="stack">
              <button id="exportWorkspaceButton" class="secondary" type="button">Export workspace</button>
              <a id="workspaceExportLink" class="download-link" hidden href="#" download="pageindex-workspace-export.zip">Download latest export</a>
              <div id="workspaceExportSummary" class="muted">No workspace export prepared.</div>
              <input id="workspaceImportPathInput" value="" placeholder="workspace export zip path" aria-label="Workspace import preview path">
              <div class="provider-actions">
                <button id="previewWorkspaceImportButton" class="secondary" type="button">Preview</button>
                <button id="restoreWorkspaceImportButton" class="secondary" type="button">Restore</button>
              </div>
              <div id="workspaceImportSummary" class="muted">No import report loaded.</div>
              <pre id="workspaceImportReportText">{}</pre>
            </div>
          </section>
          <section>
            <h2 class="section-title">Readiness</h2>
            <div class="stack">
              <div class="scope-row" aria-label="Deployment readiness options">
                <label><input id="readinessCheckProviderInput" type="checkbox">provider</label>
                <label><input id="readinessRequireProviderKeyInput" type="checkbox">key</label>
                <span></span>
              </div>
              <button id="refreshReadinessButton" class="secondary" type="button">Check readiness</button>
              <div id="readinessSummary" class="muted">Readiness not loaded.</div>
              <pre id="readinessReportText">{}</pre>
            </div>
          </section>
          <section>
            <h2 class="section-title">Provider</h2>
            <div class="stack">
              <input id="providerBaseUrlInput" value="" placeholder="base URL" aria-label="Provider base URL">
              <input id="providerModelInput" value="" placeholder="model" aria-label="Provider model">
              <input id="providerApiKeyEnvVarInput" value="" placeholder="API key env var" aria-label="Provider API key environment variable">
              <input id="providerTimeoutInput" value="" placeholder="timeout seconds" aria-label="Provider timeout seconds">
              <div class="provider-actions">
                <button id="refreshProviderButton" class="secondary" type="button">Refresh</button>
                <button id="saveProviderButton" type="button">Save</button>
                <button id="clearProviderButton" class="secondary" type="button">Clear</button>
              </div>
              <div id="providerConfigSummary" class="muted">Provider not loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Source sets</h2>
            <div class="stack">
              <input id="sourceSetNameInput" value="" placeholder="source set name" aria-label="Source set name">
              <input id="sourceSetDescriptionInput" value="" placeholder="description" aria-label="Source set description">
              <div class="provider-actions">
                <button id="refreshSourceSetsButton" class="secondary" type="button">Refresh</button>
                <button id="saveSourceSetButton" type="button">Save scope</button>
                <button id="cancelSourceSetEditButton" class="secondary" type="button" hidden>Cancel</button>
              </div>
              <div id="sourceSetList" class="member-list muted">No source sets loaded.</div>
            </div>
          </section>
          <section>
            <h2 class="section-title">Documents</h2>
            <div id="documentList" class="doc-list muted">No documents loaded.</div>
            <div id="documentAccessPanel" class="muted" style="margin-top:12px">No document access loaded.</div>
            <div id="versionList" class="version-list muted" style="margin-top:12px">No versions loaded.</div>
            <div id="pagePreviewList" class="page-list muted" style="margin-top:12px">No pages loaded.</div>
            <div id="questionSuggestionList" class="page-list muted" style="margin-top:12px">No questions loaded.</div>
            <div id="documentShareList" class="member-list muted" style="margin-top:12px">No document shares loaded.</div>
            <input id="shareUrlOutput" readonly value="" placeholder="latest share URL" aria-label="Latest share URL">
          </section>
          <div id="status" class="status"></div>
        </div>
      </aside>
      <main class="main">
        <div class="querybar">
          <textarea id="queryInput" placeholder="Ask across this workspace">margin outlook</textarea>
          <label>Hint
            <input id="hintInput" value="Streaming" placeholder="optional">
          </label>
          <span id="queryScopeLabel" class="muted">Workspace</span>
          <button id="clearQueryScopeButton" class="secondary" type="button">Clear scope</button>
          <button id="queryButton" type="button">Ask</button>
        </div>
        <div class="content">
          <section class="answer">
            <h2 class="section-title">Conversation</h2>
            <div id="messageList" class="message-list muted">No conversation selected.</div>
            <div class="chat-row" style="margin-top:12px">
              <textarea id="chatInput" placeholder="Ask in the selected conversation"></textarea>
              <button id="chatButton" type="button">Send</button>
            </div>
            <h2 class="section-title">Answer</h2>
            <div id="answerText" class="muted">Run a query to see evidence-backed output.</div>
            <h2 class="section-title" style="margin-top:18px">Citations</h2>
            <div id="citationList" class="citations muted">No citations yet.</div>
          </section>
          <section class="trace">
            <h2 class="section-title">Trace</h2>
            <pre id="traceText">{}</pre>
            <div class="doc-actions">
              <button id="refreshQueryRunsButton" class="secondary" type="button">Refresh runs</button>
            </div>
            <div class="import-row">
              <input id="queryRunActorFilterInput" value="" placeholder="actor user id" aria-label="Query run actor filter">
              <input id="queryRunSearchInput" value="" placeholder="query text" aria-label="Query run text filter">
            </div>
            <div class="import-row">
              <input id="queryRunSinceInput" value="" placeholder="since ISO time" aria-label="Query run since filter">
              <input id="queryRunUntilInput" value="" placeholder="until ISO time" aria-label="Query run until filter">
            </div>
            <div class="import-row">
              <select id="queryRunExportFormatInput" aria-label="Query run export format">
                <option value="jsonl">jsonl</option>
                <option value="csv">csv</option>
              </select>
              <button id="exportQueryRunsButton" class="secondary" type="button">Export</button>
            </div>
            <div class="import-row">
              <input id="queryRetentionDaysInput" value="" placeholder="retention days" aria-label="Query retention days">
              <button id="saveQueryRetentionButton" type="button">Save</button>
            </div>
            <div class="provider-actions">
              <button id="refreshQueryRetentionButton" class="secondary" type="button">Policy</button>
              <button id="previewQueryPurgeButton" class="secondary" type="button">Preview</button>
              <button id="purgeQueryRunsButton" class="secondary" type="button">Purge</button>
            </div>
            <div class="provider-actions">
              <button id="clearQueryRetentionButton" class="secondary" type="button">Clear retention</button>
              <button id="enableQueryLegalHoldButton" class="secondary" type="button">Hold</button>
              <button id="clearQueryLegalHoldButton" class="secondary" type="button">Release</button>
            </div>
            <input id="queryLegalHoldReasonInput" value="" placeholder="legal hold reason" aria-label="Query legal hold reason">
            <div id="queryRetentionSummary" class="muted">Retention not loaded.</div>
            <div id="queryRunList" class="query-run-list muted">No query runs loaded.</div>
            <textarea id="queryRunExportText" readonly placeholder="query run export output" aria-label="Query run export output"></textarea>
          </section>
        </div>
      </main>
    </div>
  </div>
  <script>
    const workspaceInput = document.getElementById("workspaceInput");
    const userInput = document.getElementById("userInput");
    const apiTokenInput = document.getElementById("apiTokenInput");
    const uploadInput = document.getElementById("uploadInput");
    const folderNameInput = document.getElementById("folderNameInput");
    const folderSelect = document.getElementById("folderSelect");
    const virtualNodeQueryInput = document.getElementById("virtualNodeQueryInput");
    const fileInput = document.getElementById("fileInput");
    const fileNameInput = document.getElementById("fileNameInput");
    const structureInput = document.getElementById("structureInput");
    const conversationTitleInput = document.getElementById("conversationTitleInput");
    const conversationIncludeArchivedInput = document.getElementById("conversationIncludeArchivedInput");
    const conversationExportFormatInput = document.getElementById("conversationExportFormatInput");
    const conversationExportText = document.getElementById("conversationExportText");
    const conversationShareList = document.getElementById("conversationShareList");
    const memberUserInput = document.getElementById("memberUserInput");
    const memberRoleInput = document.getElementById("memberRoleInput");
    const groupNameInput = document.getElementById("groupNameInput");
    const groupMemberUserInput = document.getElementById("groupMemberUserInput");
    const invitationEmailInput = document.getElementById("invitationEmailInput");
    const invitationExpiresInDaysInput = document.getElementById("invitationExpiresInDaysInput");
    const invitationRoleInput = document.getElementById("invitationRoleInput");
    const tokenNameInput = document.getElementById("tokenNameInput");
    const tokenExpiresInDaysInput = document.getElementById("tokenExpiresInDaysInput");
    const tokenScopeReadInput = document.getElementById("tokenScopeReadInput");
    const tokenScopeWriteInput = document.getElementById("tokenScopeWriteInput");
    const tokenScopeAuditInput = document.getElementById("tokenScopeAuditInput");
    const tokenSecretOutput = document.getElementById("tokenSecretOutput");
    const tokenPolicyDefaultExpirationInput = document.getElementById("tokenPolicyDefaultExpirationInput");
    const tokenPolicyRotationDueInput = document.getElementById("tokenPolicyRotationDueInput");
    const tokenPolicySummary = document.getElementById("tokenPolicySummary");
    const auditActionInput = document.getElementById("auditActionInput");
    const auditUserFilterInput = document.getElementById("auditUserFilterInput");
    const auditTargetTypeInput = document.getElementById("auditTargetTypeInput");
    const auditTargetIdInput = document.getElementById("auditTargetIdInput");
    const auditFormatInput = document.getElementById("auditFormatInput");
    const auditExportText = document.getElementById("auditExportText");
    const auditRetentionDaysInput = document.getElementById("auditRetentionDaysInput");
    const auditLegalHoldReasonInput = document.getElementById("auditLegalHoldReasonInput");
    const auditRetentionSummary = document.getElementById("auditRetentionSummary");
    const auditIntegritySummary = document.getElementById("auditIntegritySummary");
    const auditIntegrityReportText = document.getElementById("auditIntegrityReportText");
    const workspaceExportLink = document.getElementById("workspaceExportLink");
    const workspaceExportSummary = document.getElementById("workspaceExportSummary");
    const workspaceImportPathInput = document.getElementById("workspaceImportPathInput");
    const workspaceImportSummary = document.getElementById("workspaceImportSummary");
    const workspaceImportReportText = document.getElementById("workspaceImportReportText");
    const readinessCheckProviderInput = document.getElementById("readinessCheckProviderInput");
    const readinessRequireProviderKeyInput = document.getElementById("readinessRequireProviderKeyInput");
    const readinessSummary = document.getElementById("readinessSummary");
    const readinessReportText = document.getElementById("readinessReportText");
    const providerBaseUrlInput = document.getElementById("providerBaseUrlInput");
    const providerModelInput = document.getElementById("providerModelInput");
    const providerApiKeyEnvVarInput = document.getElementById("providerApiKeyEnvVarInput");
    const providerTimeoutInput = document.getElementById("providerTimeoutInput");
    const queryInput = document.getElementById("queryInput");
    const queryScopeLabel = document.getElementById("queryScopeLabel");
    const hintInput = document.getElementById("hintInput");
    const chatInput = document.getElementById("chatInput");
    const statusEl = document.getElementById("status");
    const documentList = document.getElementById("documentList");
    const documentAccessPanel = document.getElementById("documentAccessPanel");
    const folderAccessPanel = document.getElementById("folderAccessPanel");
    const versionList = document.getElementById("versionList");
    const pagePreviewList = document.getElementById("pagePreviewList");
    const questionSuggestionList = document.getElementById("questionSuggestionList");
    const documentShareList = document.getElementById("documentShareList");
    const shareUrlOutput = document.getElementById("shareUrlOutput");
    const folderList = document.getElementById("folderList");
    const virtualNodeList = document.getElementById("virtualNodeList");
    const conversationList = document.getElementById("conversationList");
    const memberList = document.getElementById("memberList");
    const groupList = document.getElementById("groupList");
    const usageSummary = document.getElementById("usageSummary");
    const usageReportText = document.getElementById("usageReportText");
    const quotaDocumentsInput = document.getElementById("quotaDocumentsInput");
    const quotaPagesInput = document.getElementById("quotaPagesInput");
    const quotaMembersInput = document.getElementById("quotaMembersInput");
    const quotaPolicySummary = document.getElementById("quotaPolicySummary");
    const invitationList = document.getElementById("invitationList");
    const tokenList = document.getElementById("tokenList");
    const auditList = document.getElementById("auditList");
    const providerConfigSummary = document.getElementById("providerConfigSummary");
    const messageList = document.getElementById("messageList");
    const answerText = document.getElementById("answerText");
    const citationList = document.getElementById("citationList");
    const traceText = document.getElementById("traceText");
    const queryRunList = document.getElementById("queryRunList");
    const queryRunActorFilterInput = document.getElementById("queryRunActorFilterInput");
    const queryRunSearchInput = document.getElementById("queryRunSearchInput");
    const queryRunSinceInput = document.getElementById("queryRunSinceInput");
    const queryRunUntilInput = document.getElementById("queryRunUntilInput");
    const queryRunExportFormatInput = document.getElementById("queryRunExportFormatInput");
    const queryRunExportText = document.getElementById("queryRunExportText");
    const queryRetentionDaysInput = document.getElementById("queryRetentionDaysInput");
    const queryLegalHoldReasonInput = document.getElementById("queryLegalHoldReasonInput");
    const queryRetentionSummary = document.getElementById("queryRetentionSummary");
    const sourceSetNameInput = document.getElementById("sourceSetNameInput");
    const sourceSetDescriptionInput = document.getElementById("sourceSetDescriptionInput");
    const saveSourceSetButton = document.getElementById("saveSourceSetButton");
    const cancelSourceSetEditButton = document.getElementById("cancelSourceSetEditButton");
    const sourceSetList = document.getElementById("sourceSetList");
    let activeConversationId = "";
    let activeFolderId = "";
    let activeQueryDocs = [];
    let activeQuerySourceSetId = "";
    let activeQuerySourceSetName = "";
    let editingQuerySourceSetId = "";
    let workspaceExportUrl = "";
    let currentFolders = [];
    let currentSourceSets = [];

    function headers() {
      return {
        "Content-Type": "application/json",
        ...authHeaders()
      };
    }

    function authHeaders() {
      const token = apiTokenInput.value.trim();
      if (token) {
        return {
          "Authorization": `Bearer ${token}`
        };
      }
      return {
        "X-PageIndex-Workspace": workspaceInput.value.trim(),
        "X-PageIndex-User": userInput.value.trim()
      };
    }

    function setStatus(message, tone = "") {
      statusEl.textContent = message;
      statusEl.className = `status ${tone}`;
    }

    function selectedFolderId() {
      return folderSelect.value.trim();
    }

    function withSelectedFolder(payload) {
      const folderId = selectedFolderId();
      return folderId ? { ...payload, folder_id: folderId } : payload;
    }

    function renderQueryScope() {
      if (activeQuerySourceSetId) {
        queryScopeLabel.textContent = `Set: ${activeQuerySourceSetName || activeQuerySourceSetId} (${activeQueryDocs.length} docs)`;
        return;
      }
      if (!activeQueryDocs.length) {
        queryScopeLabel.textContent = "Workspace";
        return;
      }
      const labels = activeQueryDocs.map((doc) => doc.name || doc.id);
      if (labels.length === 1) {
        queryScopeLabel.textContent = `Doc: ${labels[0]}`;
        return;
      }
      const preview = labels.slice(0, 2).join(", ");
      queryScopeLabel.textContent = `${labels.length} docs: ${preview}${labels.length > 2 ? ", ..." : ""}`;
    }

    function normalizeQueryDocument(docId, docName) {
      const id = String(docId || "").trim();
      if (!id) {
        return null;
      }
      return {
        id,
        name: String(docName || docId || "").trim() || id
      };
    }

    function setQueryDocumentScope(docId, docName) {
      const queryDoc = normalizeQueryDocument(docId, docName);
      activeQuerySourceSetId = "";
      activeQuerySourceSetName = "";
      activeQueryDocs = queryDoc ? [queryDoc] : [];
      renderQueryScope();
      queryInput.focus();
      setStatus(queryDoc ? `Query scoped to ${queryDoc.name}.` : "Query scope cleared.", queryDoc ? "ok" : "warn");
    }

    function addQueryDocumentScope(docId, docName) {
      const queryDoc = normalizeQueryDocument(docId, docName);
      if (!queryDoc) {
        setStatus("Document not found.", "warn");
        return;
      }
      activeQuerySourceSetId = "";
      activeQuerySourceSetName = "";
      const existingIndex = activeQueryDocs.findIndex((doc) => doc.id === queryDoc.id);
      if (existingIndex >= 0) {
        activeQueryDocs = activeQueryDocs.map((doc, index) => index === existingIndex ? { ...doc, name: queryDoc.name || doc.name } : doc);
      } else {
        activeQueryDocs = [...activeQueryDocs, queryDoc];
      }
      renderQueryScope();
      queryInput.focus();
      setStatus(
        existingIndex >= 0 ? `${queryDoc.name} is already in query scope.` : `Added ${queryDoc.name} to query scope (${activeQueryDocs.length} docs).`,
        "ok"
      );
    }

    function clearQueryScope() {
      activeQuerySourceSetId = "";
      activeQuerySourceSetName = "";
      setQueryDocumentScope("", "");
    }

    function pruneQueryDocumentScope(documents) {
      if (!activeQueryDocs.length) {
        return;
      }
      const availableDocIds = new Set(documents.map((doc) => String(doc.id || "")));
      const prunedDocs = activeQueryDocs.filter((doc) => availableDocIds.has(doc.id));
      if (prunedDocs.length !== activeQueryDocs.length) {
        activeQueryDocs = prunedDocs;
        renderQueryScope();
      }
    }

    function decodeQueryPayload(value) {
      if (!value) {
        return {};
      }
      try {
        const decodedValue = decodeURIComponent(value);
        const padded = decodedValue.replace(/-/g, "+").replace(/_/g, "/");
        const json = atob(padded + "=".repeat((4 - padded.length % 4) % 4));
        return JSON.parse(json);
      } catch (_error) {
        return {};
      }
    }

    function applyQueryPrefillFromLocation() {
      const params = new URLSearchParams(window.location.search);
      const payload = decodeQueryPayload(params.get("payload"));
      const query = payload.prompt || payload.query || params.get("query") || "";
      const docId = payload.doc_id || payload.docId || params.get("doc_id") || "";
      const docName = payload.doc_name || payload.docName || params.get("doc_name") || docId;
      const sourceSetId = payload.source_set_id || payload.sourceSetId || params.get("source_set_id") || "";
      const sourceSetName = payload.source_set_name || payload.sourceSetName || params.get("source_set_name") || sourceSetId;
      const payloadDocIds = Array.isArray(payload.doc_ids) ? payload.doc_ids : (Array.isArray(payload.docIds) ? payload.docIds : []);
      const payloadDocNames = Array.isArray(payload.doc_names) ? payload.doc_names : (Array.isArray(payload.docNames) ? payload.docNames : []);
      const repeatedDocIds = params.getAll("doc_id").map((value) => value.trim()).filter(Boolean);
      const listDocIds = params.getAll("doc_ids").flatMap((value) => value.split(",")).map((value) => value.trim()).filter(Boolean);
      const docIds = payloadDocIds.length ? payloadDocIds : [...listDocIds, ...(repeatedDocIds.length > 1 ? repeatedDocIds : [])];
      if (query) {
        queryInput.value = query;
      }
      if (sourceSetId) {
        activeQuerySourceSetId = String(sourceSetId).trim();
        activeQuerySourceSetName = String(sourceSetName || sourceSetId).trim();
        activeQueryDocs = [];
        renderQueryScope();
      } else if (docIds.length) {
        activeQuerySourceSetId = "";
        activeQuerySourceSetName = "";
        activeQueryDocs = docIds.map((id, index) => normalizeQueryDocument(id, payloadDocNames[index] || id)).filter(Boolean);
        renderQueryScope();
      } else if (docId) {
        setQueryDocumentScope(docId, docName);
      } else {
        renderQueryScope();
      }
      if (query || docId || docIds.length || sourceSetId) {
        setStatus("Query prefilled.", "ok");
      }
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        ...options,
        headers: { ...headers(), ...(options.headers || {}) }
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || response.statusText);
      }
      return payload;
    }

    function renderDocuments(documents) {
      if (!documents.length) {
        documentList.className = "doc-list muted";
        documentList.textContent = "No documents loaded.";
        return;
      }
      documentList.className = "doc-list";
      documentList.innerHTML = documents.map((doc) => `
        <article class="doc">
          <strong>${escapeHtml(doc.name)}</strong>
          <div class="muted">${escapeHtml(doc.kind || "unknown")} | ${escapeHtml(doc.id)}</div>
          ${doc.folder_id ? `<div class="muted">folder ${escapeHtml(doc.folder_id)}</div>` : ""}
          <div class="doc-actions">
            <button class="secondary" type="button" data-query-doc-id="${escapeHtml(doc.id)}" data-query-doc-name="${escapeHtml(doc.name)}">Ask</button>
            <button class="secondary" type="button" data-add-query-doc-id="${escapeHtml(doc.id)}" data-add-query-doc-name="${escapeHtml(doc.name)}">Scope+</button>
            <button class="secondary" type="button" data-questions-doc-id="${escapeHtml(doc.id)}" data-questions-doc-name="${escapeHtml(doc.name)}">Questions</button>
            <button class="secondary" type="button" data-pages-doc-id="${escapeHtml(doc.id)}">Preview</button>
            <button class="secondary" type="button" data-versions-doc-id="${escapeHtml(doc.id)}">Versions</button>
            <button class="secondary" type="button" data-access-doc-id="${escapeHtml(doc.id)}">Access</button>
            <button class="secondary" type="button" data-share-doc-id="${escapeHtml(doc.id)}">Share</button>
            <button class="secondary" type="button" data-shares-doc-id="${escapeHtml(doc.id)}">Shares</button>
            <button class="secondary" type="button" data-rename-doc-id="${escapeHtml(doc.id)}" data-doc-name="${escapeHtml(doc.name)}">Rename</button>
            <button class="secondary" type="button" data-move-doc-id="${escapeHtml(doc.id)}">Move</button>
            <button class="secondary" type="button" data-download-doc-id="${escapeHtml(doc.id)}">Download</button>
            <button class="secondary" type="button" data-reindex-doc-id="${escapeHtml(doc.id)}">Reindex</button>
            <button class="secondary" type="button" data-reindex-upload-doc-id="${escapeHtml(doc.id)}">Reindex upload</button>
            <button class="secondary" type="button" data-delete-doc-id="${escapeHtml(doc.id)}">Delete</button>
          </div>
        </article>
      `).join("");
      documentList.querySelectorAll("[data-query-doc-id]").forEach((button) => {
        button.addEventListener("click", () => setQueryDocumentScope(button.dataset.queryDocId, button.dataset.queryDocName));
      });
      documentList.querySelectorAll("[data-add-query-doc-id]").forEach((button) => {
        button.addEventListener("click", () => addQueryDocumentScope(button.dataset.addQueryDocId, button.dataset.addQueryDocName));
      });
      documentList.querySelectorAll("[data-questions-doc-id]").forEach((button) => {
        button.addEventListener("click", () => loadDocumentQuestions(button.dataset.questionsDocId, button.dataset.questionsDocName).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-pages-doc-id]").forEach((button) => {
        button.addEventListener("click", () => loadDocumentPages(button.dataset.pagesDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-versions-doc-id]").forEach((button) => {
        button.addEventListener("click", () => loadDocumentVersions(button.dataset.versionsDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-access-doc-id]").forEach((button) => {
        button.addEventListener("click", () => loadDocumentAccess(button.dataset.accessDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-share-doc-id]").forEach((button) => {
        button.addEventListener("click", () => createDocumentShareLink(button.dataset.shareDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-shares-doc-id]").forEach((button) => {
        button.addEventListener("click", () => loadDocumentShareLinks(button.dataset.sharesDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-rename-doc-id]").forEach((button) => {
        button.addEventListener("click", () => renameDocument(button.dataset.renameDocId, button.dataset.docName).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-move-doc-id]").forEach((button) => {
        button.addEventListener("click", () => moveDocument(button.dataset.moveDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-download-doc-id]").forEach((button) => {
        button.addEventListener("click", () => downloadDocument(button.dataset.downloadDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-reindex-doc-id]").forEach((button) => {
        button.addEventListener("click", () => reindexDocument(button.dataset.reindexDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-reindex-upload-doc-id]").forEach((button) => {
        button.addEventListener("click", () => reindexDocumentUpload(button.dataset.reindexUploadDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-delete-doc-id]").forEach((button) => {
        button.addEventListener("click", () => deleteDocument(button.dataset.deleteDocId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function sourceSetDocuments(sourceSet) {
      const docs = Array.isArray(sourceSet.documents) ? sourceSet.documents : [];
      if (docs.length) {
        return docs.map((doc) => normalizeQueryDocument(doc.id, doc.name)).filter(Boolean);
      }
      return (sourceSet.doc_ids || []).map((docId) => normalizeQueryDocument(docId, docId)).filter(Boolean);
    }

    function renderSourceSets(sourceSets) {
      currentSourceSets = sourceSets || [];
      renderSourceSetEditor();
      if (!currentSourceSets.length) {
        sourceSetList.className = "member-list muted";
        sourceSetList.textContent = "No source sets loaded.";
        return;
      }
      sourceSetList.className = "member-list";
      sourceSetList.innerHTML = currentSourceSets.map((sourceSet) => {
        const docs = sourceSetDocuments(sourceSet);
        const preview = docs.slice(0, 3).map((doc) => doc.name || doc.id).join(", ");
        return `
          <article class="member">
            <strong>${escapeHtml(sourceSet.name)}</strong>
            <div class="muted">${escapeHtml(sourceSet.id)} | ${docs.length} docs</div>
            ${sourceSet.description ? `<div class="muted">${escapeHtml(sourceSet.description)}</div>` : ""}
            ${preview ? `<div class="muted">${escapeHtml(preview)}${docs.length > 3 ? ", ..." : ""}</div>` : ""}
            <div class="doc-actions">
              <button class="secondary" type="button" data-use-source-set-id="${escapeHtml(sourceSet.id)}">Use</button>
              <button class="secondary" type="button" data-edit-source-set-id="${escapeHtml(sourceSet.id)}">Edit</button>
              <button class="secondary" type="button" data-delete-source-set-id="${escapeHtml(sourceSet.id)}">Delete</button>
            </div>
          </article>
        `;
      }).join("");
      sourceSetList.querySelectorAll("[data-use-source-set-id]").forEach((button) => {
        button.addEventListener("click", () => useQuerySourceSet(button.dataset.useSourceSetId));
      });
      sourceSetList.querySelectorAll("[data-edit-source-set-id]").forEach((button) => {
        button.addEventListener("click", () => editQuerySourceSet(button.dataset.editSourceSetId));
      });
      sourceSetList.querySelectorAll("[data-delete-source-set-id]").forEach((button) => {
        button.addEventListener("click", () => deleteQuerySourceSet(button.dataset.deleteSourceSetId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderSourceSetEditor() {
      saveSourceSetButton.textContent = editingQuerySourceSetId ? "Update scope" : "Save scope";
      cancelSourceSetEditButton.hidden = !editingQuerySourceSetId;
    }

    function useQuerySourceSet(sourceSetId) {
      const sourceSet = currentSourceSets.find((item) => item.id === sourceSetId);
      if (!sourceSet) {
        setStatus("Source set not found.", "warn");
        return;
      }
      activeQuerySourceSetId = sourceSet.id;
      activeQuerySourceSetName = sourceSet.name || sourceSet.id;
      activeQueryDocs = sourceSetDocuments(sourceSet);
      renderQueryScope();
      queryInput.focus();
      setStatus(`Query scoped to ${activeQuerySourceSetName}.`, "ok");
    }

    function editQuerySourceSet(sourceSetId) {
      const sourceSet = currentSourceSets.find((item) => item.id === sourceSetId);
      if (!sourceSet) {
        setStatus("Source set not found.", "warn");
        return;
      }
      editingQuerySourceSetId = sourceSet.id;
      sourceSetNameInput.value = sourceSet.name || "";
      sourceSetDescriptionInput.value = sourceSet.description || "";
      activeQuerySourceSetId = sourceSet.id;
      activeQuerySourceSetName = sourceSet.name || sourceSet.id;
      activeQueryDocs = sourceSetDocuments(sourceSet);
      renderQueryScope();
      renderSourceSetEditor();
      sourceSetNameInput.focus();
      setStatus("Editing source set.", "ok");
    }

    function cancelQuerySourceSetEdit(options = {}) {
      editingQuerySourceSetId = "";
      sourceSetNameInput.value = "";
      sourceSetDescriptionInput.value = "";
      renderSourceSetEditor();
      if (!options.quiet) {
        setStatus("Source set edit cancelled.", "warn");
      }
    }

    function renderDocumentAccess(docId, access) {
      if (!access) {
        documentAccessPanel.className = "muted";
        documentAccessPanel.textContent = "No document access loaded.";
        return;
      }
      const grants = access.grants || [];
      const groupGrants = access.group_grants || [];
      const grantsHtml = grants.length
        ? grants.map((grant) => `
          <article class="member">
            <div class="member-row">
              <div>
                <strong>${escapeHtml(grant.user_id)}</strong>
                <div class="muted">${escapeHtml(grant.role || "read")} | granted by ${escapeHtml(grant.granted_by || "unknown")}</div>
              </div>
              <button class="secondary" type="button" data-revoke-access-doc-id="${escapeHtml(docId)}" data-revoke-access-user-id="${escapeHtml(grant.user_id)}">Revoke</button>
            </div>
          </article>
        `).join("")
        : `<div class="muted">No direct grants.</div>`;
      const groupGrantsHtml = groupGrants.length
        ? groupGrants.map((grant) => `
          <article class="member">
            <div class="member-row">
              <div>
                <strong>${escapeHtml(grant.group_name || grant.group_id)}</strong>
                <div class="muted">${escapeHtml(grant.group_id)} | ${escapeHtml(grant.role || "read")} | granted by ${escapeHtml(grant.granted_by || "unknown")}</div>
              </div>
              <button class="secondary" type="button" data-revoke-group-access-doc-id="${escapeHtml(docId)}" data-revoke-access-group-id="${escapeHtml(grant.group_id)}">Revoke</button>
            </div>
          </article>
        `).join("")
        : `<div class="muted">No group grants.</div>`;
      documentAccessPanel.className = "stack";
      documentAccessPanel.innerHTML = `
        <article class="doc">
          <strong>${escapeHtml(docId)} access</strong>
          <div class="muted">mode ${escapeHtml(access.access_mode || "workspace")}</div>
          <div class="import-row" style="margin-top:8px">
            <select id="documentAccessModeInput" aria-label="Document access mode">
              <option value="workspace" ${access.access_mode === "workspace" ? "selected" : ""}>workspace</option>
              <option value="restricted" ${access.access_mode === "restricted" ? "selected" : ""}>restricted</option>
            </select>
            <button id="saveDocumentAccessModeButton" type="button">Save</button>
          </div>
          <div class="access-actions">
            <input id="documentAccessUserInput" value="" placeholder="user id" aria-label="Document access user id">
            <select id="documentAccessGrantRoleInput" aria-label="Document access grant role">
              <option value="read">read</option>
              <option value="write">write</option>
            </select>
            <button id="grantDocumentAccessButton" type="button">Grant</button>
            <button id="revokeDocumentAccessButton" class="secondary" type="button">Revoke</button>
          </div>
          <div class="access-actions">
            <input id="documentAccessGroupInput" value="" placeholder="group id" aria-label="Document access group id">
            <button id="grantDocumentGroupAccessButton" type="button">Grant group</button>
            <button id="revokeDocumentGroupAccessButton" class="secondary" type="button">Revoke group</button>
          </div>
        </article>
        <div class="member-list">
          <strong>Direct grants</strong>
          ${grantsHtml}
        </div>
        <div class="member-list">
          <strong>Group grants</strong>
          ${groupGrantsHtml}
        </div>
      `;
      document.getElementById("saveDocumentAccessModeButton").addEventListener("click", () => saveDocumentAccessMode(docId).catch((error) => setStatus(error.message, "error")));
      document.getElementById("grantDocumentAccessButton").addEventListener("click", () => grantDocumentAccess(docId).catch((error) => setStatus(error.message, "error")));
      document.getElementById("revokeDocumentAccessButton").addEventListener("click", () => revokeDocumentAccess(docId).catch((error) => setStatus(error.message, "error")));
      document.getElementById("grantDocumentGroupAccessButton").addEventListener("click", () => grantDocumentGroupAccess(docId).catch((error) => setStatus(error.message, "error")));
      document.getElementById("revokeDocumentGroupAccessButton").addEventListener("click", () => revokeDocumentGroupAccess(docId).catch((error) => setStatus(error.message, "error")));
      documentAccessPanel.querySelectorAll("[data-revoke-access-doc-id]").forEach((button) => {
        button.addEventListener("click", () => revokeDocumentAccess(button.dataset.revokeAccessDocId, button.dataset.revokeAccessUserId).catch((error) => setStatus(error.message, "error")));
      });
      documentAccessPanel.querySelectorAll("[data-revoke-group-access-doc-id]").forEach((button) => {
        button.addEventListener("click", () => revokeDocumentGroupAccess(button.dataset.revokeGroupAccessDocId, button.dataset.revokeAccessGroupId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderDocumentVersions(docId, versions) {
      if (!versions.length) {
        versionList.className = "version-list muted";
        versionList.textContent = "No versions loaded.";
        return;
      }
      versionList.className = "version-list";
      versionList.innerHTML = versions.map((version) => `
        <article class="version">
          <strong>v${escapeHtml(version.version)} ${escapeHtml(version.action)}</strong>
          <div class="muted">${escapeHtml(version.source_name)} | ${escapeHtml(version.created_at)}</div>
          <div class="muted">${escapeHtml(docId)} | ${escapeHtml(version.actor_user_id || "unknown")}</div>
        </article>
      `).join("");
    }

    function renderDocumentPages(docId, payload) {
      const pages = payload.pages || [];
      if (!pages.length) {
        pagePreviewList.className = "page-list muted";
        pagePreviewList.textContent = "No pages loaded.";
        return;
      }
      pagePreviewList.className = "page-list";
      pagePreviewList.innerHTML = pages.map((page) => `
        <article class="page-preview">
          <strong>${escapeHtml(docId)} page ${escapeHtml(page.page)}${page.truncated ? " (truncated)" : ""}</strong>
          <pre>${escapeHtml(page.content || "")}</pre>
        </article>
      `).join("");
    }

    function renderDocumentQuestions(docId, docName, questions) {
      if (!questions.length) {
        questionSuggestionList.className = "page-list muted";
        questionSuggestionList.textContent = "No questions loaded.";
        return;
      }
      questionSuggestionList.className = "page-list";
      questionSuggestionList.innerHTML = questions.map((question) => `
        <button class="secondary" type="button" data-suggested-question="${escapeHtml(question)}" data-suggested-doc-id="${escapeHtml(docId)}" data-suggested-doc-name="${escapeHtml(docName || docId)}">${escapeHtml(question)}</button>
      `).join("");
      questionSuggestionList.querySelectorAll("[data-suggested-question]").forEach((button) => {
        button.addEventListener("click", () => useSuggestedQuestion(button.dataset.suggestedQuestion, button.dataset.suggestedDocId, button.dataset.suggestedDocName));
      });
    }

    function shareExpiryPayload() {
      const value = window.prompt("Expires in days", "");
      if (value === null) {
        return { cancelled: true };
      }
      const trimmed = value.trim();
      if (!trimmed) {
        return { cancelled: false, payload: {} };
      }
      const days = Number(trimmed);
      if (!Number.isInteger(days) || days <= 0) {
        setStatus("Expiration days must be a positive integer.", "warn");
        return { cancelled: true };
      }
      return { cancelled: false, payload: { expires_in_days: days } };
    }

    function publicShareUrl(kind, token) {
      return `${window.location.origin}/public/${kind}/${encodeURIComponent(token)}`;
    }

    function renderShareLinks(container, kind, links) {
      if (!links.length) {
        container.className = "member-list muted";
        container.textContent = kind === "documents" ? "No document shares loaded." : "No conversation shares loaded.";
        return;
      }
      container.className = "member-list";
      const path = kind === "documents" ? "document-share-links" : "conversation-share-links";
      const targetKey = kind === "documents" ? "doc_id" : "conversation_id";
      container.innerHTML = links.map((link) => `
        <article class="member">
          <div class="member-row">
            <div>
              <strong>${escapeHtml(link.active ? "active" : "inactive")}</strong>
              <div class="muted">${escapeHtml(link.id)}${link.expires_at ? ` | expires ${escapeHtml(link.expires_at)}` : ""}</div>
            </div>
            <button class="secondary" type="button" data-revoke-share-kind="${escapeHtml(kind)}" data-revoke-share-target-id="${escapeHtml(link[targetKey] || "")}" data-revoke-share-link-path="${escapeHtml(path)}" data-revoke-share-link-id="${escapeHtml(link.id)}"${link.active ? "" : " disabled"}>Revoke</button>
          </div>
        </article>
      `).join("");
      container.querySelectorAll("[data-revoke-share-link-id]").forEach((button) => {
        button.addEventListener("click", () => revokeShareLink(button.dataset.revokeShareLinkPath, button.dataset.revokeShareLinkId, button.dataset.revokeShareKind, button.dataset.revokeShareTargetId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderFolders(folders, selectedId = activeFolderId) {
      currentFolders = folders;
      const exists = folders.some((folder) => folder.id === selectedId);
      activeFolderId = exists ? selectedId : "";
      folderSelect.innerHTML = `<option value="">No folder</option>` + folders.map((folder) => `
        <option value="${escapeHtml(folder.id)}">${escapeHtml(folder.path || folder.name || folder.id)}</option>
      `).join("");
      folderSelect.value = activeFolderId;
      if (!folders.length) {
        folderList.className = "folder-list muted";
        folderList.textContent = "No folders loaded.";
        return;
      }
      folderList.className = "folder-list";
      folderList.innerHTML = folders.map((folder) => `
        <article class="folder ${folder.id === activeFolderId ? "active" : ""}" data-folder-id="${escapeHtml(folder.id)}">
          <strong>${escapeHtml(folder.name)}</strong>
          <div class="muted">${escapeHtml(folder.path)}</div>
          <div class="doc-actions">
            <button class="secondary" type="button" data-select-folder-id="${escapeHtml(folder.id)}">Select</button>
            <button class="secondary" type="button" data-rename-folder-id="${escapeHtml(folder.id)}">Rename</button>
            <button class="secondary" type="button" data-move-folder-id="${escapeHtml(folder.id)}">Move</button>
            <button class="secondary" type="button" data-delete-folder-id="${escapeHtml(folder.id)}">Delete</button>
          </div>
        </article>
      `).join("");
      folderList.querySelectorAll("[data-select-folder-id]").forEach((button) => {
        button.addEventListener("click", () => {
          activeFolderId = button.dataset.selectFolderId || "";
          folderSelect.value = activeFolderId;
          renderFolders(folders, activeFolderId);
          const selected = folders.find((folder) => folder.id === activeFolderId);
          setStatus(selected ? `Folder selected ${selected.path}.` : "No folder selected.", "ok");
        });
      });
      folderList.querySelectorAll("[data-rename-folder-id]").forEach((button) => {
        button.addEventListener("click", () => renameFolder(button.dataset.renameFolderId).catch((error) => setStatus(error.message, "error")));
      });
      folderList.querySelectorAll("[data-move-folder-id]").forEach((button) => {
        button.addEventListener("click", () => moveFolder(button.dataset.moveFolderId).catch((error) => setStatus(error.message, "error")));
      });
      folderList.querySelectorAll("[data-delete-folder-id]").forEach((button) => {
        button.addEventListener("click", () => deleteFolder(button.dataset.deleteFolderId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderFolderAccess(access) {
      if (!access) {
        folderAccessPanel.className = "muted";
        folderAccessPanel.textContent = "No folder access loaded.";
        return;
      }
      const grants = access.grants || [];
      const groupGrants = access.group_grants || [];
      const folder = access.folder || {};
      const grantsHtml = grants.length
        ? grants.map((grant) => `
          <article class="member">
            <div class="member-row">
              <div>
                <strong>${escapeHtml(grant.user_id)}</strong>
                <div class="muted">${escapeHtml(grant.role || "read")} | granted by ${escapeHtml(grant.granted_by || "unknown")}</div>
              </div>
              <button class="secondary" type="button" data-revoke-folder-access-user-id="${escapeHtml(grant.user_id)}">Revoke</button>
            </div>
          </article>
        `).join("")
        : `<div class="muted">No direct folder grants.</div>`;
      const groupGrantsHtml = groupGrants.length
        ? groupGrants.map((grant) => `
          <article class="member">
            <div class="member-row">
              <div>
                <strong>${escapeHtml(grant.group_name || grant.group_id)}</strong>
                <div class="muted">${escapeHtml(grant.group_id)} | ${escapeHtml(grant.role || "read")} | granted by ${escapeHtml(grant.granted_by || "unknown")}</div>
              </div>
              <button class="secondary" type="button" data-revoke-folder-access-group-id="${escapeHtml(grant.group_id)}">Revoke</button>
            </div>
          </article>
        `).join("")
        : `<div class="muted">No folder group grants.</div>`;
      folderAccessPanel.className = "stack";
      folderAccessPanel.innerHTML = `
        <article class="folder">
          <strong>${escapeHtml(folder.path || folder.name || folder.id || "Folder")}</strong>
          <div class="muted">inherited by descendant folders</div>
        </article>
        <div class="member-list">
          <strong>Direct folder grants</strong>
          ${grantsHtml}
        </div>
        <div class="member-list">
          <strong>Folder group grants</strong>
          ${groupGrantsHtml}
        </div>
      `;
      folderAccessPanel.querySelectorAll("[data-revoke-folder-access-user-id]").forEach((button) => {
        button.addEventListener("click", () => revokeFolderAccess(button.dataset.revokeFolderAccessUserId).catch((error) => setStatus(error.message, "error")));
      });
      folderAccessPanel.querySelectorAll("[data-revoke-folder-access-group-id]").forEach((button) => {
        button.addEventListener("click", () => revokeFolderGroupAccess(button.dataset.revokeFolderAccessGroupId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderVirtualNodes(nodes) {
      if (!nodes.length) {
        virtualNodeList.className = "virtual-node-list muted";
        virtualNodeList.textContent = "No virtual nodes loaded.";
        return;
      }
      virtualNodeList.className = "virtual-node-list";
      virtualNodeList.innerHTML = nodes.map((node) => {
        const score = node.score == null ? "" : ` | score ${node.score}`;
        return `
          <article class="virtual-node">
            <strong>${escapeHtml(node.label || node.path)}</strong>
            <div class="muted">${escapeHtml(node.axis || "virtual")} | docs ${escapeHtml(node.doc_count || 0)}${escapeHtml(score)}</div>
            <div class="muted">${escapeHtml(node.path || node.id)}</div>
          </article>
        `;
      }).join("");
    }

    function renderCitations(citations) {
      if (!citations.length) {
        citationList.className = "citations muted";
        citationList.textContent = "No citations returned.";
        return;
      }
      citationList.className = "citations";
      citationList.innerHTML = citations.map((citation) => `
        <article class="citation">
          <strong>${escapeHtml(citation.label)}</strong>
          <div class="muted">${escapeHtml(citation.doc_id)}</div>
        </article>
      `).join("");
    }

    function renderQueryRuns(runs) {
      if (!runs.length) {
        queryRunList.className = "query-run-list muted";
        queryRunList.textContent = "No query runs loaded.";
        return;
      }
      queryRunList.className = "query-run-list";
      queryRunList.innerHTML = runs.map((run) => `
        <article class="query-run">
          <strong>${escapeHtml(run.query || run.id)}</strong>
          <div class="muted">${escapeHtml(run.id)} | user ${escapeHtml(run.actor_user_id || "unknown")} | evidence ${escapeHtml(run.evidence_count || 0)} | citations ${escapeHtml(run.citation_count || 0)}</div>
          <div class="muted">${escapeHtml(run.completed_at || run.created_at || "")}</div>
          <div class="doc-actions">
            <button class="secondary" type="button" data-query-run-id="${escapeHtml(run.id)}">Trace</button>
            <button class="secondary" type="button" data-delete-query-run-id="${escapeHtml(run.id)}">Delete</button>
          </div>
        </article>
      `).join("");
      queryRunList.querySelectorAll("[data-query-run-id]").forEach((button) => {
        button.addEventListener("click", () => loadQueryRunTrace(button.dataset.queryRunId).catch((error) => setStatus(error.message, "error")));
      });
      queryRunList.querySelectorAll("[data-delete-query-run-id]").forEach((button) => {
        button.addEventListener("click", () => deleteQueryRun(button.dataset.deleteQueryRunId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderQueryRetention(policy) {
      const holdText = policy && policy.legal_hold ? "legal hold on" : "legal hold off";
      const holdReason = policy && policy.legal_hold_reason ? ` | reason ${policy.legal_hold_reason}` : "";
      queryLegalHoldReasonInput.value = policy && policy.legal_hold_reason ? policy.legal_hold_reason : "";
      if (!policy || policy.retention_days == null) {
        queryRetentionDaysInput.value = "";
        queryRetentionSummary.className = policy && policy.legal_hold ? "status warn" : "muted";
        queryRetentionSummary.textContent = `Retention not set. | ${holdText}${holdReason}`;
        return;
      }
      queryRetentionDaysInput.value = String(policy.retention_days);
      queryRetentionSummary.className = policy.legal_hold ? "status warn" : "muted";
      queryRetentionSummary.textContent = `${policy.retention_days} days | ${holdText}${holdReason} | updated ${policy.updated_at || "unknown"}`;
    }

    function renderQueryPurgeResult(result) {
      const action = result.dry_run ? "Preview" : "Purge";
      queryRetentionSummary.className = result.purged > 0 ? "status warn" : "muted";
      queryRetentionSummary.textContent = `${action}: matched ${result.matched}, purged ${result.purged}`;
    }

    function renderConversations(conversations) {
      if (!conversations.length) {
        conversationList.className = "conversation-list muted";
        conversationList.textContent = "No conversations loaded.";
        return;
      }
      conversationList.className = "conversation-list";
      conversationList.innerHTML = conversations.map((conversation) => `
        <article class="conversation ${conversation.id === activeConversationId ? "active" : ""}">
          <button class="secondary" type="button" data-conversation-id="${escapeHtml(conversation.id)}">
            <strong>${escapeHtml(conversation.title)}</strong>
            <div class="muted">${escapeHtml(conversation.message_count || 0)} messages${conversation.archived_at ? " | archived" : ""}${conversation.source_set_id ? ` | source set ${escapeHtml(conversation.source_set_id)}` : ""}</div>
          </button>
          <div class="doc-actions">
            <button class="secondary" type="button" data-rename-conversation-id="${escapeHtml(conversation.id)}" data-conversation-title="${escapeHtml(conversation.title)}">Rename</button>
            <button class="secondary" type="button" data-share-conversation-id="${escapeHtml(conversation.id)}">Share</button>
            <button class="secondary" type="button" data-shares-conversation-id="${escapeHtml(conversation.id)}">Shares</button>
            <button class="secondary" type="button" data-archive-conversation-id="${escapeHtml(conversation.id)}" data-archive-state="${conversation.archived_at ? "restore" : "archive"}">${conversation.archived_at ? "Restore" : "Archive"}</button>
            <button class="secondary" type="button" data-delete-conversation-id="${escapeHtml(conversation.id)}">Delete</button>
          </div>
        </article>
      `).join("");
      conversationList.querySelectorAll("[data-conversation-id]").forEach((button) => {
        button.addEventListener("click", () => selectConversation(button.dataset.conversationId));
      });
      conversationList.querySelectorAll("[data-rename-conversation-id]").forEach((button) => {
        button.addEventListener("click", () => renameConversation(button.dataset.renameConversationId, button.dataset.conversationTitle).catch((error) => setStatus(error.message, "error")));
      });
      conversationList.querySelectorAll("[data-share-conversation-id]").forEach((button) => {
        button.addEventListener("click", () => createConversationShareLink(button.dataset.shareConversationId).catch((error) => setStatus(error.message, "error")));
      });
      conversationList.querySelectorAll("[data-shares-conversation-id]").forEach((button) => {
        button.addEventListener("click", () => loadConversationShareLinks(button.dataset.sharesConversationId).catch((error) => setStatus(error.message, "error")));
      });
      conversationList.querySelectorAll("[data-archive-conversation-id]").forEach((button) => {
        button.addEventListener("click", () => archiveConversation(button.dataset.archiveConversationId, button.dataset.archiveState === "restore").catch((error) => setStatus(error.message, "error")));
      });
      conversationList.querySelectorAll("[data-delete-conversation-id]").forEach((button) => {
        button.addEventListener("click", () => deleteConversation(button.dataset.deleteConversationId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderMembers(members) {
      if (!members.length) {
        memberList.className = "member-list muted";
        memberList.textContent = "No members loaded.";
        return;
      }
      memberList.className = "member-list";
      memberList.innerHTML = members.map((member) => `
        <article class="member">
          <div class="member-row">
            <div>
              <strong>${escapeHtml(member.user_id)}</strong>
              <div class="muted">${escapeHtml(member.role)}</div>
            </div>
            <button class="secondary" type="button" data-remove-member-user-id="${escapeHtml(member.user_id)}">Remove</button>
          </div>
        </article>
      `).join("");
      memberList.querySelectorAll("[data-remove-member-user-id]").forEach((button) => {
        button.addEventListener("click", () => removeMember(button.dataset.removeMemberUserId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderGroups(groups, membersByGroup = {}) {
      if (!groups.length) {
        groupList.className = "group-list muted";
        groupList.textContent = "No groups loaded.";
        return;
      }
      groupList.className = "group-list";
      groupList.innerHTML = groups.map((group) => {
        const members = membersByGroup[group.id] || [];
        const memberRows = members.length
          ? members.map((member) => `
            <div class="member-row">
              <div>
                <strong>${escapeHtml(member.user_id)}</strong>
                <div class="muted">${escapeHtml(member.created_at || "member")}</div>
              </div>
              <button class="secondary" type="button" data-remove-group-member-id="${escapeHtml(group.id)}" data-remove-group-member-user-id="${escapeHtml(member.user_id)}">Remove</button>
            </div>
          `).join("")
          : `<div class="muted">No group members.</div>`;
        return `
          <article class="member" data-group-id="${escapeHtml(group.id)}">
            <strong>${escapeHtml(group.name)}</strong>
            <div class="muted">${escapeHtml(group.id)} | ${escapeHtml(group.member_count || 0)} members</div>
            <div class="doc-actions">
              <button class="secondary" type="button" data-add-group-member-id="${escapeHtml(group.id)}">Add</button>
              <button class="secondary" type="button" data-rename-group-id="${escapeHtml(group.id)}">Rename</button>
              <button class="secondary" type="button" data-refresh-group-members-id="${escapeHtml(group.id)}">Members</button>
              <button class="secondary" type="button" data-delete-group-id="${escapeHtml(group.id)}">Delete</button>
            </div>
            <div class="stack" style="margin-top:8px">${memberRows}</div>
          </article>
        `;
      }).join("");
      groupList.querySelectorAll("[data-add-group-member-id]").forEach((button) => {
        button.addEventListener("click", () => addGroupMember(button.dataset.addGroupMemberId).catch((error) => setStatus(error.message, "error")));
      });
      groupList.querySelectorAll("[data-rename-group-id]").forEach((button) => {
        button.addEventListener("click", () => renameGroup(button.dataset.renameGroupId).catch((error) => setStatus(error.message, "error")));
      });
      groupList.querySelectorAll("[data-refresh-group-members-id]").forEach((button) => {
        button.addEventListener("click", () => refreshGroups().catch((error) => setStatus(error.message, "error")));
      });
      groupList.querySelectorAll("[data-delete-group-id]").forEach((button) => {
        button.addEventListener("click", () => deleteGroup(button.dataset.deleteGroupId).catch((error) => setStatus(error.message, "error")));
      });
      groupList.querySelectorAll("[data-remove-group-member-id]").forEach((button) => {
        button.addEventListener("click", () => removeGroupMember(button.dataset.removeGroupMemberId, button.dataset.removeGroupMemberUserId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderWorkspaceUsage(usage) {
      if (!usage) {
        usageSummary.className = "muted";
        usageSummary.textContent = "Usage not loaded.";
        usageReportText.textContent = "{}";
        return;
      }
      const documents = usage.documents || {};
      const team = usage.team || {};
      const tokens = usage.api_tokens || {};
      const conversations = usage.conversations || {};
      const retrieval = usage.retrieval || {};
      const audit = usage.audit || {};
      usageSummary.className = "muted";
      usageSummary.textContent = `${documents.count || 0} docs | ${documents.pages || 0} pages | ${team.members || 0} members | ${team.groups || 0} groups | ${tokens.active || 0} tokens | ${conversations.count || 0} chats | ${retrieval.query_runs || 0} queries | ${audit.events || 0} audit events`;
      usageReportText.textContent = JSON.stringify(usage, null, 2);
    }

    function quotaLimitText(limit) {
      return limit == null ? "unlimited" : String(limit);
    }

    function renderWorkspaceQuotaPolicy(policy) {
      if (!policy) {
        quotaDocumentsInput.value = "";
        quotaPagesInput.value = "";
        quotaMembersInput.value = "";
        quotaPolicySummary.className = "muted";
        quotaPolicySummary.textContent = "Quota not loaded.";
        return;
      }
      const maxDocuments = policy.max_documents == null ? null : policy.max_documents;
      const maxPages = policy.max_pages == null ? null : policy.max_pages;
      const maxMembers = policy.max_members == null ? null : policy.max_members;
      const usage = policy.usage || {};
      const violations = Array.isArray(policy.violations) ? policy.violations : [];
      quotaDocumentsInput.value = maxDocuments == null ? "" : String(maxDocuments);
      quotaPagesInput.value = maxPages == null ? "" : String(maxPages);
      quotaMembersInput.value = maxMembers == null ? "" : String(maxMembers);
      const usageText = `${usage.documents || 0}/${quotaLimitText(maxDocuments)} docs | ${usage.pages || 0}/${quotaLimitText(maxPages)} pages | ${usage.members || 0}/${quotaLimitText(maxMembers)} members`;
      const violationText = violations.length ? ` | over ${violations.join(", ")}` : "";
      const updatedText = policy.updated_at ? ` | updated ${policy.updated_at}` : "";
      quotaPolicySummary.className = policy.within_quota === false ? "status warn" : "muted";
      quotaPolicySummary.textContent = `${usageText}${violationText}${updatedText}`;
    }

    function renderInvitations(invitations) {
      if (!invitations.length) {
        invitationList.className = "member-list muted";
        invitationList.textContent = "No invitations loaded.";
        return;
      }
      invitationList.className = "member-list";
      invitationList.innerHTML = invitations.map((invitation) => `
        <article class="member">
          <div class="member-row">
            <div>
              <strong>${escapeHtml(invitation.email)}</strong>
              <div class="muted">${escapeHtml(invitation.role)} | ${escapeHtml(invitation.status)}${invitation.expires_at ? ` | expires ${escapeHtml(invitation.expires_at)}` : ""}</div>
            </div>
            ${invitation.status === "pending" ? `<button class="secondary" type="button" data-revoke-invitation-id="${escapeHtml(invitation.id)}">Revoke</button>` : ""}
          </div>
        </article>
      `).join("");
      invitationList.querySelectorAll("[data-revoke-invitation-id]").forEach((button) => {
        button.addEventListener("click", () => revokeInvitation(button.dataset.revokeInvitationId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderApiTokens(tokens) {
      if (!tokens.length) {
        tokenList.className = "token-list muted";
        tokenList.textContent = "No tokens loaded.";
        return;
      }
      tokenList.className = "token-list";
      tokenList.innerHTML = tokens.map((token) => {
        const scopes = Array.isArray(token.scopes) ? token.scopes.join(", ") : "";
        const expiry = token.expires_at || "no expiration";
        const rotation = token.rotation_due_at ? ` | rotation ${token.rotation_due_at}` : "";
        return `
          <article class="token" data-token-name="${escapeHtml(token.name)}">
            <strong>${escapeHtml(token.name)}</strong>
            <div class="muted">${escapeHtml(token.id)}</div>
            <div class="muted">${escapeHtml(scopes)} | ${escapeHtml(expiry)}${escapeHtml(rotation)}</div>
            <div class="token-actions">
              <button class="secondary" type="button" data-rotate-token-id="${escapeHtml(token.id)}">Rotate</button>
              <button class="secondary" type="button" data-revoke-token-id="${escapeHtml(token.id)}">Revoke</button>
            </div>
          </article>
        `;
      }).join("");
      tokenList.querySelectorAll("[data-rotate-token-id]").forEach((button) => {
        button.addEventListener("click", () => rotateApiToken(button.dataset.rotateTokenId).catch((error) => setStatus(error.message, "error")));
      });
      tokenList.querySelectorAll("[data-revoke-token-id]").forEach((button) => {
        button.addEventListener("click", () => revokeApiToken(button.dataset.revokeTokenId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderApiTokenPolicy(policy) {
      const defaultDays = policy && policy.default_expires_in_days != null ? policy.default_expires_in_days : null;
      const rotationDays = policy && policy.rotation_due_in_days != null ? policy.rotation_due_in_days : null;
      tokenPolicyDefaultExpirationInput.value = defaultDays == null ? "" : String(defaultDays);
      tokenPolicyRotationDueInput.value = rotationDays == null ? "" : String(rotationDays);
      if (defaultDays == null && rotationDays == null) {
        tokenPolicySummary.className = "muted";
        tokenPolicySummary.textContent = "Policy not set.";
        return;
      }
      const defaultText = defaultDays == null ? "default unset" : `default ${defaultDays} days`;
      const rotationText = rotationDays == null ? "rotation unset" : `rotation ${rotationDays} days`;
      tokenPolicySummary.className = "muted";
      tokenPolicySummary.textContent = `${defaultText} | ${rotationText}${policy && policy.updated_at ? ` | updated ${policy.updated_at}` : ""}`;
    }

    function renderAuditEvents(events) {
      if (!events.length) {
        auditList.className = "audit-list muted";
        auditList.textContent = "No audit events loaded.";
        return;
      }
      auditList.className = "audit-list";
      auditList.innerHTML = events.map((event) => `
        <article class="audit-event" data-audit-action="${escapeHtml(event.action)}">
          <strong>${escapeHtml(event.action)}</strong>
          <div class="muted">${escapeHtml(event.created_at)} | ${escapeHtml(event.target_type)} ${escapeHtml(event.target_id || "")}</div>
          <pre>${escapeHtml(JSON.stringify(event.details || {}, null, 2))}</pre>
        </article>
      `).join("");
    }

    function renderAuditRetention(policy) {
      const holdText = policy && policy.legal_hold ? "legal hold on" : "legal hold off";
      const holdReason = policy && policy.legal_hold_reason ? ` | reason ${policy.legal_hold_reason}` : "";
      auditLegalHoldReasonInput.value = policy && policy.legal_hold_reason ? policy.legal_hold_reason : "";
      if (!policy || policy.retention_days == null) {
        auditRetentionDaysInput.value = "";
        auditRetentionSummary.className = policy && policy.legal_hold ? "status warn" : "muted";
        auditRetentionSummary.textContent = `Retention not set. | ${holdText}${holdReason}`;
        return;
      }
      auditRetentionDaysInput.value = String(policy.retention_days);
      auditRetentionSummary.className = policy.legal_hold ? "status warn" : "muted";
      auditRetentionSummary.textContent = `${policy.retention_days} days | ${holdText}${holdReason} | updated ${policy.updated_at || "unknown"}`;
    }

    function renderAuditPurgeResult(result) {
      const action = result.dry_run ? "Preview" : "Purge";
      auditRetentionSummary.className = result.purged > 0 ? "status warn" : "muted";
      auditRetentionSummary.textContent = `${action}: matched ${result.matched}, purged ${result.purged}`;
    }

    function renderAuditIntegrity(report) {
      const checked = report && Number.isFinite(Number(report.checked)) ? Number(report.checked) : 0;
      const legacy = report && Number.isFinite(Number(report.legacy)) ? Number(report.legacy) : 0;
      const failures = report && Number.isFinite(Number(report.failure_count)) ? Number(report.failure_count) : 0;
      if (report && report.ok) {
        auditIntegritySummary.className = "status ok";
        auditIntegritySummary.textContent = `Ledger verified: ${checked} hashed events, ${legacy} legacy, ${failures} failures.`;
      } else {
        auditIntegritySummary.className = "status error";
        auditIntegritySummary.textContent = `Ledger check failed: ${checked} hashed events, ${legacy} legacy, ${failures} failures.`;
      }
      auditIntegrityReportText.textContent = JSON.stringify(report || {}, null, 2);
    }

    function renderWorkspaceImportReport(report, label) {
      const errors = Array.isArray(report.errors) ? report.errors.length : 0;
      const warnings = Array.isArray(report.warnings) ? report.warnings.length : 0;
      const tables = report.table_counts || {};
      const tableTotal = Object.keys(tables).length;
      const docs = tables.documents == null ? 0 : tables.documents;
      workspaceImportSummary.className = report.ok ? "status ok" : "status error";
      workspaceImportSummary.textContent = `${label} ${report.ok ? "ok" : "failed"}: ${tableTotal} tables, ${docs} documents, ${errors} errors, ${warnings} warnings`;
      workspaceImportReportText.textContent = JSON.stringify(report, null, 2);
    }

    function renderWorkspaceImportPreview(report) {
      renderWorkspaceImportReport(report, "Preview");
    }

    function renderWorkspaceImportRestore(report) {
      renderWorkspaceImportReport(report, "Restore");
    }

    function renderDeploymentReadiness(report) {
      const summary = report.summary || { passed: 0, total: 0 };
      readinessSummary.className = report.ok ? "status ok" : "status error";
      readinessSummary.textContent = `${report.ok ? "Ready" : "Not ready"}: ${summary.passed}/${summary.total} checks`;
      readinessReportText.textContent = JSON.stringify(report, null, 2);
    }

    function renderProviderConfig(config) {
      if (!config || !config.configured) {
        providerBaseUrlInput.value = "";
        providerModelInput.value = "";
        providerApiKeyEnvVarInput.value = "";
        providerTimeoutInput.value = "";
        providerConfigSummary.className = "muted";
        providerConfigSummary.textContent = "Provider not configured.";
        return;
      }
      providerBaseUrlInput.value = config.base_url || "";
      providerModelInput.value = config.model || "";
      providerApiKeyEnvVarInput.value = config.api_key_env_var || "";
      providerTimeoutInput.value = config.timeout_seconds == null ? "" : String(config.timeout_seconds);
      const keyState = config.api_key_env_var ? (config.api_key_configured ? "key env set" : "key env unset") : "no key env";
      providerConfigSummary.className = "muted";
      providerConfigSummary.textContent = `${config.provider || "openai-compatible"} | ${config.model || "no model"} | ${keyState}`;
    }

    function renderMessages(messages) {
      if (!messages.length) {
        messageList.className = "message-list muted";
        messageList.textContent = activeConversationId ? "No messages yet." : "No conversation selected.";
        return;
      }
      messageList.className = "message-list";
      messageList.innerHTML = messages.map((message) => `
        <article class="message ${escapeHtml(message.role)}">
          <strong>${escapeHtml(message.role)}</strong>
          <div>${escapeHtml(message.content)}</div>
        </article>
      `).join("");
    }

    async function refreshDocuments() {
      setStatus("Refreshing...");
      const payload = await api("/documents");
      const documents = payload.documents || [];
      pruneQueryDocumentScope(documents);
      renderDocuments(documents);
      setStatus("Documents refreshed.", "ok");
    }

    async function refreshQuerySourceSets(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing source sets...");
      }
      const payload = await api("/query-source-sets");
      renderSourceSets(payload.source_sets || []);
      if (!options.quiet) {
        setStatus("Source sets refreshed.", "ok");
      }
    }

    async function saveQuerySourceSet() {
      const name = sourceSetNameInput.value.trim();
      if (!name) {
        setStatus("Source set name is required.", "warn");
        return;
      }
      const docIds = activeQueryDocs.map((doc) => doc.id);
      if (!docIds.length) {
        setStatus("Choose one or more scoped documents first.", "warn");
        return;
      }
      setStatus(editingQuerySourceSetId ? "Updating source set..." : "Saving source set...");
      const sourceSetPath = editingQuerySourceSetId ? `/query-source-sets/${encodeURIComponent(editingQuerySourceSetId)}` : "/query-source-sets";
      const wasEditing = Boolean(editingQuerySourceSetId);
      const payload = await api(sourceSetPath, {
        method: editingQuerySourceSetId ? "PUT" : "POST",
        body: JSON.stringify({
          name,
          description: sourceSetDescriptionInput.value.trim(),
          doc_ids: docIds
        })
      });
      editingQuerySourceSetId = "";
      sourceSetNameInput.value = "";
      sourceSetDescriptionInput.value = "";
      renderSourceSetEditor();
      renderSourceSets([payload, ...currentSourceSets.filter((sourceSet) => sourceSet.id !== payload.id)]);
      useQuerySourceSet(payload.id);
      setStatus(wasEditing ? "Source set updated." : "Source set saved.", "ok");
    }

    async function deleteQuerySourceSet(sourceSetId) {
      if (!sourceSetId) {
        setStatus("Source set not found.", "warn");
        return;
      }
      if (!window.confirm("Delete this source set?")) {
        setStatus("Source set delete cancelled.", "warn");
        return;
      }
      setStatus("Deleting source set...");
      const result = await api(`/query-source-sets/${encodeURIComponent(sourceSetId)}`, {
        method: "DELETE"
      });
      await refreshQuerySourceSets({ quiet: true });
      if (editingQuerySourceSetId === sourceSetId) {
        cancelQuerySourceSetEdit({ quiet: true });
      }
      if (activeQuerySourceSetId === sourceSetId) {
        clearQueryScope();
      }
      setStatus(result.deleted ? "Source set deleted." : "Source set not found.", result.deleted ? "ok" : "warn");
    }

    async function loadDocumentVersions(docId) {
      if (!docId) {
        setStatus("Document not found.", "warn");
        return;
      }
      setStatus("Refreshing versions...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}/versions`);
      renderDocumentVersions(docId, payload.versions || []);
      setStatus("Versions refreshed.", "ok");
    }

    async function loadDocumentPages(docId) {
      if (!docId) {
        setStatus("Document not found.", "warn");
        return;
      }
      setStatus("Loading pages...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}/pages?limit=5&max_chars=2000`);
      renderDocumentPages(docId, payload);
      setStatus("Pages refreshed.", "ok");
    }

    async function loadDocumentQuestions(docId, docName) {
      if (!docId) {
        setStatus("Document not found.", "warn");
        return;
      }
      setStatus("Loading questions...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}/suggested-questions?limit=5`);
      renderDocumentQuestions(docId, docName || docId, payload.questions || []);
      setStatus("Questions loaded.", "ok");
    }

    function useSuggestedQuestion(question, docId, docName) {
      queryInput.value = question || "";
      setQueryDocumentScope(docId || "", docName || docId || "");
    }

    async function loadDocumentShareLinks(docId) {
      if (!docId) {
        setStatus("Document not found.", "warn");
        return;
      }
      setStatus("Loading document shares...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}/share-links`);
      renderShareLinks(documentShareList, "documents", payload.share_links || []);
      setStatus("Document shares loaded.", "ok");
    }

    async function createDocumentShareLink(docId) {
      if (!docId) {
        setStatus("Document not found.", "warn");
        return;
      }
      const expiry = shareExpiryPayload();
      if (expiry.cancelled) {
        return;
      }
      setStatus("Creating document share...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}/share-links`, {
        method: "POST",
        body: JSON.stringify(expiry.payload)
      });
      const link = payload.share_link || {};
      shareUrlOutput.value = link.token ? publicShareUrl("documents", link.token) : "";
      await loadDocumentShareLinks(docId);
      setStatus("Document share created.", "ok");
    }

    async function loadDocumentAccess(docId) {
      if (!docId) {
        setStatus("Document not found.", "warn");
        return;
      }
      setStatus("Loading access...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}/access`);
      renderDocumentAccess(docId, payload.access);
      setStatus("Access refreshed.", "ok");
    }

    async function updateDocumentAccess(docId, payload, message) {
      const updated = await api(`/documents/${encodeURIComponent(docId)}/access`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      renderDocumentAccess(docId, updated.access);
      setStatus(message, "ok");
    }

    async function saveDocumentAccessMode(docId) {
      const input = document.getElementById("documentAccessModeInput");
      await updateDocumentAccess(docId, { access_mode: input.value }, "Access mode saved.");
    }

    async function grantDocumentAccess(docId) {
      const input = document.getElementById("documentAccessUserInput");
      const roleInput = document.getElementById("documentAccessGrantRoleInput");
      const userId = input.value.trim();
      if (!userId) {
        setStatus("Enter a user id.", "warn");
        return;
      }
      await updateDocumentAccess(docId, { grant_user_id: userId, grant_role: roleInput.value }, "Document access granted.");
    }

    async function revokeDocumentAccess(docId, userId = "") {
      const input = document.getElementById("documentAccessUserInput");
      const targetUserId = (userId || (input ? input.value : "")).trim();
      if (!targetUserId) {
        setStatus("Enter a user id.", "warn");
        return;
      }
      await updateDocumentAccess(docId, { revoke_user_id: targetUserId }, "Document access revoked.");
    }

    async function grantDocumentGroupAccess(docId, groupId = "") {
      const input = document.getElementById("documentAccessGroupInput");
      const roleInput = document.getElementById("documentAccessGrantRoleInput");
      const targetGroupId = (groupId || (input ? input.value : "")).trim();
      if (!targetGroupId) {
        setStatus("Enter a group id.", "warn");
        return;
      }
      await updateDocumentAccess(docId, { grant_group_id: targetGroupId, grant_role: roleInput.value }, "Document group access granted.");
    }

    async function revokeDocumentGroupAccess(docId, groupId = "") {
      const input = document.getElementById("documentAccessGroupInput");
      const targetGroupId = (groupId || (input ? input.value : "")).trim();
      if (!targetGroupId) {
        setStatus("Enter a group id.", "warn");
        return;
      }
      await updateDocumentAccess(docId, { revoke_group_id: targetGroupId }, "Document group access revoked.");
    }

    async function loadFolderAccess(folderId = selectedFolderId()) {
      if (!folderId) {
        setStatus("Select a folder.", "warn");
        return;
      }
      setStatus("Refreshing folder access...");
      const payload = await api(`/folders/${encodeURIComponent(folderId)}/access`);
      renderFolderAccess(payload.access);
      setStatus("Folder access refreshed.", "ok");
    }

    async function updateFolderAccess(folderId, payload, message) {
      const updated = await api(`/folders/${encodeURIComponent(folderId)}/access`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      renderFolderAccess(updated.access);
      setStatus(message, "ok");
    }

    async function grantFolderAccess() {
      const folderId = selectedFolderId();
      const input = document.getElementById("folderAccessUserInput");
      const userId = input.value.trim();
      if (!folderId) {
        setStatus("Select a folder.", "warn");
        return;
      }
      if (!userId) {
        setStatus("Enter a user id.", "warn");
        return;
      }
      await updateFolderAccess(folderId, { grant_user_id: userId }, "Folder access granted.");
    }

    async function revokeFolderAccess(userId = "") {
      const folderId = selectedFolderId();
      const input = document.getElementById("folderAccessUserInput");
      const targetUserId = (userId || (input ? input.value : "")).trim();
      if (!folderId) {
        setStatus("Select a folder.", "warn");
        return;
      }
      if (!targetUserId) {
        setStatus("Enter a user id.", "warn");
        return;
      }
      await updateFolderAccess(folderId, { revoke_user_id: targetUserId }, "Folder access revoked.");
    }

    async function grantFolderGroupAccess() {
      const folderId = selectedFolderId();
      const input = document.getElementById("folderAccessGroupInput");
      const groupId = input.value.trim();
      if (!folderId) {
        setStatus("Select a folder.", "warn");
        return;
      }
      if (!groupId) {
        setStatus("Enter a group id.", "warn");
        return;
      }
      await updateFolderAccess(folderId, { grant_group_id: groupId }, "Folder group access granted.");
    }

    async function revokeFolderGroupAccess(groupId = "") {
      const folderId = selectedFolderId();
      const input = document.getElementById("folderAccessGroupInput");
      const targetGroupId = (groupId || (input ? input.value : "")).trim();
      if (!folderId) {
        setStatus("Select a folder.", "warn");
        return;
      }
      if (!targetGroupId) {
        setStatus("Enter a group id.", "warn");
        return;
      }
      await updateFolderAccess(folderId, { revoke_group_id: targetGroupId }, "Folder group access revoked.");
    }

    async function refreshFolders(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing folders...");
      }
      const payload = await api("/folders");
      renderFolders(payload.folders || [], options.selectedFolderId || activeFolderId);
      if (!options.quiet) {
        setStatus("Folders refreshed.", "ok");
      }
    }

    async function refreshVirtualNodes(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing virtual nodes...");
      }
      const payload = await api("/virtual-nodes");
      renderVirtualNodes(payload.nodes || []);
      if (!options.quiet) {
        setStatus("Virtual nodes refreshed.", "ok");
      }
    }

    async function planVirtualNodes() {
      const query = virtualNodeQueryInput.value.trim();
      if (!query) {
        setStatus("Enter a virtual-node query.", "warn");
        return;
      }
      setStatus("Planning virtual nodes...");
      const params = new URLSearchParams({ query, limit: "10" });
      const payload = await api(`/virtual-nodes?${params.toString()}`);
      renderVirtualNodes(payload.nodes || []);
      setStatus("Virtual node plan refreshed.", "ok");
    }

    async function refreshConversations() {
      setStatus("Refreshing chats...");
      const params = new URLSearchParams();
      if (conversationIncludeArchivedInput.checked) {
        params.set("include_archived", "true");
      }
      const suffix = params.toString() ? `?${params.toString()}` : "";
      const payload = await api(`/conversations${suffix}`);
      const conversations = payload.conversations || [];
      if (activeConversationId && !conversations.some((conversation) => conversation.id === activeConversationId)) {
        activeConversationId = "";
        renderMessages([]);
      }
      renderConversations(conversations);
      setStatus("Chats refreshed.", "ok");
    }

    async function refreshMembers() {
      setStatus("Refreshing team...");
      const payload = await api("/workspace-members");
      renderMembers(payload.members || []);
      setStatus("Team refreshed.", "ok");
    }

    async function refreshGroups(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing groups...");
      }
      const payload = await api("/workspace-groups");
      const groups = payload.groups || [];
      const entries = await Promise.all(groups.map(async (group) => {
        const memberPayload = await api(`/workspace-groups/${encodeURIComponent(group.id)}/members`);
        return [group.id, memberPayload.members || []];
      }));
      renderGroups(groups, Object.fromEntries(entries));
      if (!options.quiet) {
        setStatus("Groups refreshed.", "ok");
      }
    }

    async function refreshUsage(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing usage...");
      }
      const payload = await api("/workspace-usage");
      renderWorkspaceUsage(payload.usage);
      if (!options.quiet) {
        setStatus("Usage refreshed.", "ok");
      }
    }

    async function refreshWorkspaceQuotaPolicy(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing quota policy...");
      }
      const policy = await api("/workspace-quota-policy");
      renderWorkspaceQuotaPolicy(policy);
      if (!options.quiet) {
        setStatus("Quota policy refreshed.", "ok");
      }
    }

    async function refreshInvitations(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing invites...");
      }
      const payload = await api("/workspace-invitations");
      renderInvitations(payload.invitations || []);
      if (!options.quiet) {
        setStatus("Invitations refreshed.", "ok");
      }
    }

    async function refreshApiTokens(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing tokens...");
      }
      const payload = await api("/api-tokens");
      renderApiTokens(payload.tokens || []);
      if (!options.quiet) {
        setStatus("Tokens refreshed.", "ok");
      }
    }

    async function refreshApiTokenPolicy(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing token policy...");
      }
      const policy = await api("/api-token-policy");
      renderApiTokenPolicy(policy);
      if (!options.quiet) {
        setStatus("Token policy refreshed.", "ok");
      }
    }

    function auditQueryString(options = {}) {
      const params = new URLSearchParams();
      const action = auditActionInput.value.trim();
      const eventUser = auditUserFilterInput.value.trim();
      const targetType = auditTargetTypeInput.value.trim();
      const targetId = auditTargetIdInput.value.trim();
      if (action) {
        params.set("action", action);
      }
      if (eventUser) {
        params.set("event_user_id", eventUser);
      }
      if (targetType) {
        params.set("target_type", targetType);
      }
      if (targetId) {
        params.set("target_id", targetId);
      }
      if (options.format) {
        params.set("format", options.format);
      } else {
        params.set("limit", "20");
      }
      const query = params.toString();
      return query ? `?${query}` : "";
    }

    async function refreshAuditEvents(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing audit...");
      }
      const payload = await api(`/audit-events${auditQueryString()}`);
      renderAuditEvents(payload.events || []);
      if (!options.quiet) {
        setStatus("Audit refreshed.", "ok");
      }
    }

    async function refreshAuditRetention(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing retention...");
      }
      const policy = await api("/audit-retention");
      renderAuditRetention(policy);
      if (!options.quiet) {
        setStatus("Retention refreshed.", "ok");
      }
    }

    async function verifyAuditIntegrity(options = {}) {
      if (!options.quiet) {
        setStatus("Verifying audit ledger...");
      }
      const report = await api("/audit-integrity");
      renderAuditIntegrity(report);
      if (!options.quiet) {
        setStatus(report.ok ? "Audit ledger verified." : "Audit ledger failed.", report.ok ? "ok" : "error");
      }
    }

    function readinessQueryString() {
      const params = new URLSearchParams();
      if (readinessCheckProviderInput.checked) {
        params.set("check_provider", "1");
      }
      if (readinessRequireProviderKeyInput.checked) {
        params.set("require_provider_api_key", "1");
      }
      const query = params.toString();
      return query ? `?${query}` : "";
    }

    async function refreshDeploymentReadiness(options = {}) {
      if (!options.quiet) {
        setStatus("Checking readiness...");
      }
      const report = await api(`/deployment-check${readinessQueryString()}`);
      renderDeploymentReadiness(report);
      if (!options.quiet) {
        setStatus("Readiness refreshed.", "ok");
      }
    }

    async function refreshAll() {
      await refreshFolders({ quiet: true });
      try {
        await refreshVirtualNodes({ quiet: true });
      } catch (error) {
        virtualNodeList.className = "virtual-node-list muted";
        virtualNodeList.textContent = "Virtual nodes unavailable.";
      }
      await refreshDocuments();
      try {
        await refreshQuerySourceSets({ quiet: true });
      } catch (error) {
        sourceSetList.className = "member-list muted";
        sourceSetList.textContent = "Source sets unavailable.";
      }
      await refreshConversations();
      try {
        await refreshMembers();
      } catch (error) {
        memberList.className = "member-list muted";
        memberList.textContent = "Team unavailable.";
        setStatus("Documents and chats refreshed.", "ok");
      }
      try {
        await refreshGroups({ quiet: true });
      } catch (error) {
        groupList.className = "group-list muted";
        groupList.textContent = "Groups unavailable.";
      }
      try {
        await refreshUsage({ quiet: true });
      } catch (error) {
        usageSummary.className = "muted";
        usageSummary.textContent = "Usage unavailable.";
        usageReportText.textContent = "{}";
      }
      try {
        await refreshWorkspaceQuotaPolicy({ quiet: true });
      } catch (error) {
        renderWorkspaceQuotaPolicy(null);
        quotaPolicySummary.textContent = "Quota unavailable.";
      }
      try {
        await refreshInvitations({ quiet: true });
      } catch (error) {
        invitationList.className = "member-list muted";
        invitationList.textContent = "Invitations unavailable.";
      }
      try {
        await refreshApiTokens({ quiet: true });
      } catch (error) {
        tokenList.className = "token-list muted";
        tokenList.textContent = "Tokens unavailable.";
      }
      try {
        await refreshApiTokenPolicy({ quiet: true });
      } catch (error) {
        tokenPolicySummary.className = "muted";
        tokenPolicySummary.textContent = "Token policy unavailable.";
      }
      try {
        await refreshAuditEvents({ quiet: true });
      } catch (error) {
        auditList.className = "audit-list muted";
        auditList.textContent = "Audit unavailable.";
      }
      try {
        await refreshAuditRetention({ quiet: true });
      } catch (error) {
        auditRetentionSummary.className = "muted";
        auditRetentionSummary.textContent = "Retention unavailable.";
      }
      try {
        await verifyAuditIntegrity({ quiet: true });
      } catch (error) {
        auditIntegritySummary.className = "muted";
        auditIntegritySummary.textContent = "Integrity unavailable.";
      }
      try {
        await refreshQueryRetention({ quiet: true });
      } catch (error) {
        queryRetentionSummary.className = "muted";
        queryRetentionSummary.textContent = "Retention unavailable.";
      }
      try {
        await refreshDeploymentReadiness({ quiet: true });
      } catch (error) {
        readinessSummary.className = "muted";
        readinessSummary.textContent = "Readiness unavailable.";
      }
      try {
        await refreshProviderConfig({ quiet: true });
      } catch (error) {
        renderProviderConfig(null);
        providerConfigSummary.className = "muted";
        providerConfigSummary.textContent = "Provider unavailable.";
      }
    }

    async function createFolder() {
      const name = folderNameInput.value.trim();
      if (!name) {
        setStatus("Enter a folder name.", "warn");
        return;
      }
      const payload = { name };
      const parentId = selectedFolderId();
      if (parentId) {
        payload.parent_id = parentId;
      }
      setStatus("Creating folder...");
      const created = await api("/folders", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      folderNameInput.value = "";
      await refreshFolders({ quiet: true, selectedFolderId: created.folder_id });
      setStatus("Folder created.", "ok");
    }

    async function renameFolder(folderId) {
      const name = folderNameInput.value.trim();
      if (!folderId) {
        setStatus("Folder not found.", "warn");
        return;
      }
      if (!name) {
        setStatus("Enter a folder name.", "warn");
        return;
      }
      setStatus("Renaming folder...");
      const payload = await api(`/folders/${encodeURIComponent(folderId)}`, {
        method: "PUT",
        body: JSON.stringify({ name })
      });
      folderNameInput.value = "";
      await refreshFolders({ quiet: true, selectedFolderId: payload.folder ? payload.folder.id : folderId });
      setStatus("Folder renamed.", "ok");
    }

    async function moveFolder(folderId) {
      if (!folderId) {
        setStatus("Folder not found.", "warn");
        return;
      }
      const parentId = selectedFolderId();
      if (parentId === folderId) {
        setStatus("Choose a different parent folder.", "warn");
        return;
      }
      const payload = parentId ? { parent_id: parentId } : {};
      setStatus("Moving folder...");
      const moved = await api(`/folders/${encodeURIComponent(folderId)}/move`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      await refreshFolders({ quiet: true, selectedFolderId: moved.folder ? moved.folder.id : folderId });
      setStatus("Folder moved.", "ok");
    }

    async function deleteFolder(folderId) {
      if (!folderId) {
        setStatus("Folder not found.", "warn");
        return;
      }
      setStatus("Deleting folder...");
      const payload = await api(`/folders/${encodeURIComponent(folderId)}`, {
        method: "DELETE"
      });
      if (payload.deleted && activeFolderId === folderId) {
        activeFolderId = "";
        folderSelect.value = "";
        renderFolderAccess(null);
      }
      await refreshFolders({ quiet: true });
      setStatus(payload.deleted ? "Folder deleted." : "Folder not found.", payload.deleted ? "ok" : "warn");
    }

    async function createConversation() {
      const title = conversationTitleInput.value.trim();
      const body = { title: title || undefined };
      if (activeQuerySourceSetId) {
        body.source_set_id = activeQuerySourceSetId;
      }
      setStatus("Creating chat...");
      const conversation = await api("/conversations", {
        method: "POST",
        body: JSON.stringify(body)
      });
      activeConversationId = conversation.id;
      conversationTitleInput.value = "";
      await refreshConversations();
      await loadConversationMessages(activeConversationId);
      setStatus("Conversation created.", "ok");
    }

    async function selectConversation(conversationId) {
      activeConversationId = conversationId;
      await refreshConversations();
      await loadConversationMessages(conversationId);
    }

    async function loadConversationMessages(conversationId) {
      if (!conversationId) {
        renderMessages([]);
        return;
      }
      const payload = await api(`/conversations/${conversationId}/messages`);
      renderMessages(payload.messages || []);
    }

    async function exportConversation() {
      if (!activeConversationId) {
        setStatus("Select a conversation.", "warn");
        return;
      }
      setStatus("Exporting conversation...");
      const params = new URLSearchParams({ format: conversationExportFormatInput.value });
      const response = await fetch(`/conversations/${encodeURIComponent(activeConversationId)}/export?${params.toString()}`, {
        headers: authHeaders()
      });
      const text = await response.text();
      if (!response.ok) {
        try {
          const payload = JSON.parse(text);
          throw new Error(payload.error || response.statusText);
        } catch (error) {
          if (error instanceof SyntaxError) {
            throw new Error(response.statusText);
          }
          throw error;
        }
      }
      conversationExportText.value = text;
      setStatus("Conversation exported.", "ok");
    }

    async function loadConversationShareLinks(conversationId) {
      if (!conversationId) {
        setStatus("Conversation not found.", "warn");
        return;
      }
      setStatus("Loading conversation shares...");
      const payload = await api(`/conversations/${encodeURIComponent(conversationId)}/share-links`);
      renderShareLinks(conversationShareList, "conversations", payload.share_links || []);
      setStatus("Conversation shares loaded.", "ok");
    }

    async function createConversationShareLink(conversationId) {
      if (!conversationId) {
        setStatus("Conversation not found.", "warn");
        return;
      }
      const expiry = shareExpiryPayload();
      if (expiry.cancelled) {
        return;
      }
      setStatus("Creating conversation share...");
      const payload = await api(`/conversations/${encodeURIComponent(conversationId)}/share-links`, {
        method: "POST",
        body: JSON.stringify(expiry.payload)
      });
      const link = payload.share_link || {};
      shareUrlOutput.value = link.token ? publicShareUrl("conversations", link.token) : "";
      await loadConversationShareLinks(conversationId);
      setStatus("Conversation share created.", "ok");
    }

    async function revokeShareLink(path, shareLinkId, kind, targetId) {
      if (!path || !shareLinkId) {
        setStatus("Share link not found.", "warn");
        return;
      }
      if (!window.confirm("Revoke this share link?")) {
        setStatus("Share revoke cancelled.", "warn");
        return;
      }
      setStatus("Revoking share...");
      const payload = await api(`/${path}/${encodeURIComponent(shareLinkId)}`, {
        method: "DELETE"
      });
      setStatus(payload.revoked ? "Share revoked." : "Share not found.", payload.revoked ? "ok" : "warn");
      if (kind === "documents" && targetId) {
        await loadDocumentShareLinks(targetId).catch(() => {});
      } else if (kind === "conversations" && targetId) {
        await loadConversationShareLinks(targetId).catch(() => {});
      } else if (activeConversationId) {
        await loadConversationShareLinks(activeConversationId).catch(() => {});
      }
    }

    async function renameConversation(conversationId, currentTitle) {
      const title = window.prompt("Rename conversation", currentTitle || "");
      if (title === null) {
        setStatus("Conversation rename cancelled.", "warn");
        return;
      }
      const trimmed = title.trim();
      if (!trimmed) {
        setStatus("Conversation title required.", "warn");
        return;
      }
      setStatus("Renaming conversation...");
      await api(`/conversations/${encodeURIComponent(conversationId)}/rename`, {
        method: "POST",
        body: JSON.stringify({ title: trimmed })
      });
      await refreshConversations();
      setStatus("Conversation renamed.", "ok");
    }

    async function archiveConversation(conversationId, restore = false) {
      if (!window.confirm(restore ? "Restore this conversation?" : "Archive this conversation?")) {
        setStatus(restore ? "Restore cancelled." : "Archive cancelled.", "warn");
        return;
      }
      setStatus(restore ? "Restoring conversation..." : "Archiving conversation...");
      await api(`/conversations/${encodeURIComponent(conversationId)}/archive`, {
        method: "POST",
        body: JSON.stringify({ archived: !restore })
      });
      if (!restore && activeConversationId === conversationId) {
        activeConversationId = "";
        renderMessages([]);
      }
      await refreshConversations();
      setStatus(restore ? "Conversation restored." : "Conversation archived.", "ok");
    }

    async function deleteConversation(conversationId) {
      if (!window.confirm("Delete this conversation?")) {
        setStatus("Delete cancelled.", "warn");
        return;
      }
      setStatus("Deleting conversation...");
      const payload = await api(`/conversations/${encodeURIComponent(conversationId)}`, {
        method: "DELETE"
      });
      if (payload.deleted && activeConversationId === conversationId) {
        activeConversationId = "";
        renderMessages([]);
      }
      await refreshConversations();
      setStatus(payload.deleted ? "Conversation deleted." : "Conversation not found.", payload.deleted ? "ok" : "warn");
    }

    async function saveMember() {
      const userId = memberUserInput.value.trim();
      if (!userId) {
        setStatus("Enter a user id.", "warn");
        return;
      }
      setStatus("Saving member...");
      await api("/workspace-members", {
        method: "POST",
        body: JSON.stringify({ user_id: userId, role: memberRoleInput.value })
      });
      memberUserInput.value = "";
      await refreshMembers();
      setStatus("Member saved.", "ok");
    }

    async function removeMember(userId) {
      setStatus("Removing member...");
      const payload = await api(`/workspace-members/${encodeURIComponent(userId)}`, {
        method: "DELETE"
      });
      await refreshMembers();
      setStatus(payload.removed ? "Member removed." : "Member not found.", payload.removed ? "ok" : "warn");
    }

    async function createGroup() {
      const name = groupNameInput.value.trim();
      if (!name) {
        setStatus("Enter a group name.", "warn");
        return;
      }
      setStatus("Creating group...");
      await api("/workspace-groups", {
        method: "POST",
        body: JSON.stringify({ name })
      });
      groupNameInput.value = "";
      await refreshGroups({ quiet: true });
      setStatus("Group created.", "ok");
    }

    async function addGroupMember(groupId) {
      const userId = groupMemberUserInput.value.trim();
      if (!groupId) {
        setStatus("Group not found.", "warn");
        return;
      }
      if (!userId) {
        setStatus("Enter a group member user id.", "warn");
        return;
      }
      setStatus("Adding group member...");
      await api(`/workspace-groups/${encodeURIComponent(groupId)}/members`, {
        method: "POST",
        body: JSON.stringify({ user_id: userId })
      });
      groupMemberUserInput.value = "";
      await refreshGroups({ quiet: true });
      setStatus("Group member added.", "ok");
    }

    async function renameGroup(groupId) {
      const name = groupNameInput.value.trim();
      if (!groupId) {
        setStatus("Group not found.", "warn");
        return;
      }
      if (!name) {
        setStatus("Enter a group name.", "warn");
        return;
      }
      setStatus("Renaming group...");
      await api(`/workspace-groups/${encodeURIComponent(groupId)}`, {
        method: "PUT",
        body: JSON.stringify({ name })
      });
      groupNameInput.value = "";
      await refreshGroups({ quiet: true });
      setStatus("Group renamed.", "ok");
    }

    async function deleteGroup(groupId) {
      if (!groupId) {
        setStatus("Group not found.", "warn");
        return;
      }
      setStatus("Deleting group...");
      const payload = await api(`/workspace-groups/${encodeURIComponent(groupId)}`, {
        method: "DELETE"
      });
      await refreshGroups({ quiet: true });
      setStatus(payload.deleted ? "Group deleted." : "Group not found.", payload.deleted ? "ok" : "warn");
    }

    async function removeGroupMember(groupId, userId) {
      if (!groupId || !userId) {
        setStatus("Group member not found.", "warn");
        return;
      }
      setStatus("Removing group member...");
      const payload = await api(`/workspace-groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(userId)}`, {
        method: "DELETE"
      });
      await refreshGroups({ quiet: true });
      setStatus(payload.removed ? "Group member removed." : "Group member not found.", payload.removed ? "ok" : "warn");
    }

    function invitationExpiresInDays() {
      const value = invitationExpiresInDaysInput.value.trim();
      if (!value) {
        return null;
      }
      const days = Number(value);
      if (!Number.isInteger(days) || days <= 0) {
        setStatus("Invitation expiration days must be a positive integer.", "warn");
        return undefined;
      }
      return days;
    }

    async function createInvitation() {
      const email = invitationEmailInput.value.trim();
      if (!email) {
        setStatus("Enter an invitation email.", "warn");
        return;
      }
      const expiresInDays = invitationExpiresInDays();
      if (expiresInDays === undefined) {
        return;
      }
      const payload = {
        email,
        role: invitationRoleInput.value
      };
      if (expiresInDays !== null) {
        payload.expires_in_days = expiresInDays;
      }
      setStatus("Creating invitation...");
      await api("/workspace-invitations", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      invitationEmailInput.value = "";
      invitationExpiresInDaysInput.value = "";
      await refreshInvitations({ quiet: true });
      setStatus("Invitation created.", "ok");
    }

    async function revokeInvitation(invitationId) {
      if (!invitationId) {
        setStatus("Invitation not found.", "warn");
        return;
      }
      setStatus("Revoking invitation...");
      const payload = await api(`/workspace-invitations/${encodeURIComponent(invitationId)}`, {
        method: "DELETE"
      });
      await refreshInvitations({ quiet: true });
      setStatus(payload.revoked ? "Invitation revoked." : "Invitation not found.", payload.revoked ? "ok" : "warn");
    }

    function selectedTokenScopes() {
      const scopes = [];
      if (tokenScopeReadInput.checked) {
        scopes.push("read");
      }
      if (tokenScopeWriteInput.checked) {
        scopes.push("write");
      }
      if (tokenScopeAuditInput.checked) {
        scopes.push("audit");
      }
      return scopes;
    }

    async function createApiToken() {
      const scopes = selectedTokenScopes();
      if (!scopes.length) {
        setStatus("Choose at least one token scope.", "warn");
        return;
      }
      const payload = { scopes };
      const name = tokenNameInput.value.trim();
      if (name) {
        payload.name = name;
      }
      const expiresInDays = tokenExpiresInDaysInput.value.trim();
      if (expiresInDays) {
        const days = Number(expiresInDays);
        if (!Number.isInteger(days) || days <= 0) {
          setStatus("Token expiration days must be a positive integer.", "warn");
          return;
        }
        payload.expires_in_days = days;
      }
      setStatus("Creating token...");
      const created = await api("/api-tokens", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      tokenNameInput.value = "";
      tokenSecretOutput.value = created.token && created.token.token ? created.token.token : "";
      await refreshApiTokens({ quiet: true });
      setStatus("Token created.", "ok");
    }

    function tokenPolicyDaysValue(input, label) {
      const value = input.value.trim();
      if (!value) {
        return { valid: true, days: null };
      }
      const days = Number(value);
      if (!Number.isInteger(days) || days <= 0) {
        setStatus(`${label} must be a positive integer.`, "warn");
        return { valid: false, days: null };
      }
      return { valid: true, days };
    }

    async function saveApiTokenPolicy() {
      const defaultValue = tokenPolicyDaysValue(tokenPolicyDefaultExpirationInput, "Default expiration days");
      const rotationValue = tokenPolicyDaysValue(tokenPolicyRotationDueInput, "Rotation due days");
      if (!defaultValue.valid || !rotationValue.valid) {
        return;
      }
      const payload = {
        default_expires_in_days: defaultValue.days,
        rotation_due_in_days: rotationValue.days
      };
      setStatus("Saving token policy...");
      const policy = await api("/api-token-policy", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      renderApiTokenPolicy(policy);
      setStatus("Token policy saved.", "ok");
    }

    async function clearApiTokenPolicy() {
      setStatus("Clearing token policy...");
      const policy = await api("/api-token-policy", {
        method: "POST",
        body: JSON.stringify({ clear_default_expiration: true, clear_rotation_due: true })
      });
      renderApiTokenPolicy(policy);
      setStatus("Token policy cleared.", "ok");
    }

    function quotaLimitValue(input, label) {
      const value = input.value.trim();
      if (!value) {
        return { valid: true, limit: null };
      }
      const limit = Number(value);
      if (!Number.isInteger(limit) || limit <= 0) {
        setStatus(`${label} must be a positive integer.`, "warn");
        return { valid: false, limit: null };
      }
      return { valid: true, limit };
    }

    async function saveWorkspaceQuotaPolicy() {
      const documents = quotaLimitValue(quotaDocumentsInput, "Max documents");
      const pages = quotaLimitValue(quotaPagesInput, "Max pages");
      const members = quotaLimitValue(quotaMembersInput, "Max members");
      if (!documents.valid || !pages.valid || !members.valid) {
        return;
      }
      setStatus("Saving quota policy...");
      const policy = await api("/workspace-quota-policy", {
        method: "POST",
        body: JSON.stringify({
          max_documents: documents.limit,
          max_pages: pages.limit,
          max_members: members.limit
        })
      });
      renderWorkspaceQuotaPolicy(policy);
      setStatus("Quota policy saved.", "ok");
    }

    async function clearWorkspaceQuotaPolicy() {
      setStatus("Clearing quota policy...");
      const policy = await api("/workspace-quota-policy", {
        method: "POST",
        body: JSON.stringify({ max_documents: null, max_pages: null, max_members: null })
      });
      renderWorkspaceQuotaPolicy(policy);
      setStatus("Quota policy cleared.", "ok");
    }

    async function rotateApiToken(tokenId) {
      if (!tokenId) {
        setStatus("Token not found.", "warn");
        return;
      }
      setStatus("Rotating token...");
      const rotated = await api(`/api-tokens/${encodeURIComponent(tokenId)}/rotate`, {
        method: "POST",
        body: JSON.stringify({})
      });
      tokenSecretOutput.value = rotated.token && rotated.token.token ? rotated.token.token : "";
      await refreshApiTokens({ quiet: true });
      setStatus("Token rotated.", "ok");
    }

    async function revokeApiToken(tokenId) {
      if (!tokenId) {
        setStatus("Token not found.", "warn");
        return;
      }
      setStatus("Revoking token...");
      const payload = await api(`/api-tokens/${encodeURIComponent(tokenId)}`, {
        method: "DELETE"
      });
      await refreshApiTokens({ quiet: true });
      setStatus(payload.revoked ? "Token revoked." : "Token not found.", payload.revoked ? "ok" : "warn");
    }

    async function exportAuditEvents() {
      setStatus("Exporting audit...");
      const response = await fetch(`/audit-events/export${auditQueryString({ format: auditFormatInput.value })}`, {
        headers: authHeaders()
      });
      const text = await response.text();
      if (!response.ok) {
        try {
          const payload = JSON.parse(text);
          throw new Error(payload.error || response.statusText);
        } catch (error) {
          if (error instanceof SyntaxError) {
            throw new Error(response.statusText);
          }
          throw error;
        }
      }
      auditExportText.value = text;
      setStatus("Audit exported.", "ok");
    }

    function filenameFromDisposition(value, fallback = "pageindex-workspace-export.zip") {
      const match = /filename="([^"]+)"/.exec(value || "");
      return match ? match[1] : fallback;
    }

    async function exportWorkspaceBundle() {
      setStatus("Exporting workspace...");
      const response = await fetch("/workspace-export", {
        headers: authHeaders()
      });
      if (!response.ok) {
        const text = await response.text();
        try {
          const payload = JSON.parse(text);
          throw new Error(payload.error || response.statusText);
        } catch (error) {
          if (error instanceof SyntaxError) {
            throw new Error(response.statusText);
          }
          throw error;
        }
      }
      const blob = await response.blob();
      if (workspaceExportUrl) {
        URL.revokeObjectURL(workspaceExportUrl);
      }
      workspaceExportUrl = URL.createObjectURL(blob);
      workspaceExportLink.href = workspaceExportUrl;
      workspaceExportLink.download = filenameFromDisposition(response.headers.get("Content-Disposition"));
      workspaceExportLink.hidden = false;
      workspaceExportSummary.textContent = `workspace export ready (${blob.size} bytes)`;
      setStatus("Workspace export prepared.", "ok");
    }

    async function previewWorkspaceImport() {
      const path = workspaceImportPathInput.value.trim();
      if (!path) {
        setStatus("Enter a workspace export zip path.", "warn");
        return;
      }
      setStatus("Previewing import...");
      const report = await api("/workspace-import/preview", {
        method: "POST",
        body: JSON.stringify({ path })
      });
      renderWorkspaceImportPreview(report);
      setStatus(report.ok ? "Import preview passed." : "Import preview failed.", report.ok ? "ok" : "warn");
    }

    async function restoreWorkspaceImport() {
      const path = workspaceImportPathInput.value.trim();
      if (!path) {
        setStatus("Enter a workspace export zip path.", "warn");
        return;
      }
      if (!window.confirm("Restore this workspace export bundle?")) {
        setStatus("Restore cancelled.", "warn");
        return;
      }
      setStatus("Restoring workspace...");
      const report = await api("/workspace-import", {
        method: "POST",
        body: JSON.stringify({ path })
      });
      renderWorkspaceImportRestore(report);
      setStatus(report.ok ? "Workspace restored." : "Workspace restore failed.", report.ok ? "ok" : "warn");
    }

    function parsedRetentionDays() {
      const value = auditRetentionDaysInput.value.trim();
      if (!value) {
        setStatus("Enter retention days.", "warn");
        return null;
      }
      const days = Number(value);
      if (!Number.isInteger(days) || days <= 0) {
        setStatus("Retention days must be a positive integer.", "warn");
        return null;
      }
      return days;
    }

    async function saveAuditRetention() {
      const days = parsedRetentionDays();
      if (days == null) {
        return;
      }
      setStatus("Saving retention...");
      const policy = await api("/audit-retention", {
        method: "POST",
        body: JSON.stringify({ retention_days: days })
      });
      renderAuditRetention(policy);
      setStatus("Retention saved.", "ok");
    }

    async function clearAuditRetention() {
      setStatus("Clearing retention...");
      const policy = await api("/audit-retention", {
        method: "POST",
        body: JSON.stringify({ clear: true })
      });
      renderAuditRetention(policy);
      setStatus("Retention cleared.", "ok");
    }

    async function setAuditLegalHold(enabled) {
      setStatus(enabled ? "Enabling legal hold..." : "Releasing legal hold...");
      const reason = auditLegalHoldReasonInput.value.trim();
      const body = enabled && reason ? { legal_hold: true, legal_hold_reason: reason } : { legal_hold: enabled };
      const policy = await api("/audit-retention", {
        method: "POST",
        body: JSON.stringify(body)
      });
      renderAuditRetention(policy);
      setStatus(enabled ? "Legal hold enabled." : "Legal hold released.", "ok");
    }

    async function previewAuditPurge() {
      setStatus("Previewing purge...");
      const result = await api("/audit-retention/purge", {
        method: "POST",
        body: JSON.stringify({ dry_run: true })
      });
      renderAuditPurgeResult(result);
      setStatus("Retention previewed.", "ok");
    }

    async function purgeAuditEvents() {
      if (!window.confirm("Permanently purge audit events older than the retention policy?")) {
        setStatus("Purge cancelled.", "warn");
        return;
      }
      setStatus("Purging audit...");
      const result = await api("/audit-retention/purge", {
        method: "POST",
        body: JSON.stringify({})
      });
      renderAuditPurgeResult(result);
      await refreshAuditEvents({ quiet: true });
      setStatus("Audit purged.", "ok");
    }

    async function refreshProviderConfig(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing provider...");
      }
      const config = await api("/provider-config");
      renderProviderConfig(config);
      if (!options.quiet) {
        setStatus("Provider refreshed.", "ok");
      }
    }

    async function saveProviderConfig() {
      const baseUrl = providerBaseUrlInput.value.trim();
      const model = providerModelInput.value.trim();
      if (!baseUrl || !model) {
        setStatus("Enter provider base URL and model.", "warn");
        return;
      }
      const payload = {
        base_url: baseUrl,
        model
      };
      const apiKeyEnvVar = providerApiKeyEnvVarInput.value.trim();
      if (apiKeyEnvVar) {
        payload.api_key_env_var = apiKeyEnvVar;
      }
      const timeout = providerTimeoutInput.value.trim();
      if (timeout) {
        const timeoutSeconds = Number(timeout);
        if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
          setStatus("Provider timeout must be positive.", "warn");
          return;
        }
        payload.timeout_seconds = timeoutSeconds;
      }
      setStatus("Saving provider...");
      const config = await api("/provider-config", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      renderProviderConfig(config);
      setStatus("Provider saved.", "ok");
    }

    async function clearProviderConfig() {
      setStatus("Clearing provider...");
      const config = await api("/provider-config", {
        method: "POST",
        body: JSON.stringify({ clear: true })
      });
      renderProviderConfig(config);
      setStatus("Provider cleared.", "ok");
    }

    async function sendChatMessage() {
      if (!activeConversationId) {
        setStatus("Select a conversation.", "warn");
        return;
      }
      const message = chatInput.value.trim();
      if (!message) {
        setStatus("Enter a message.", "warn");
        return;
      }
      setStatus("Sending...");
      const payload = await api(`/conversations/${activeConversationId}/messages`, {
        method: "POST",
        body: JSON.stringify({ message, expert_hints: hintInput.value.trim() ? [hintInput.value.trim()] : [] })
      });
      chatInput.value = "";
      await loadConversationMessages(activeConversationId);
      await refreshConversations();
      answerText.className = "";
      answerText.textContent = payload.result && payload.result.answer ? payload.result.answer : "No answer returned.";
      renderCitations(payload.result && payload.result.citations ? payload.result.citations : []);
      traceText.textContent = JSON.stringify(payload.result && payload.result.trace ? payload.result.trace : {}, null, 2);
      const ok = payload.result && payload.result.verification && payload.result.verification.ok;
      setStatus(ok ? "Conversation trace verified." : "Conversation trace returned warnings.", ok ? "ok" : "warn");
    }

    async function importStructure() {
      const path = structureInput.value.trim();
      if (!path) {
        setStatus("Enter a structure JSON path.", "warn");
        return;
      }
      setStatus("Importing...");
      const payload = await api("/import-structure", {
        method: "POST",
        body: JSON.stringify(withSelectedFolder({ path }))
      });
      setStatus(`Imported ${payload.doc_id}.`, "ok");
      await refreshDocuments();
    }

    async function ingestFile() {
      const path = fileInput.value.trim();
      if (!path) {
        setStatus("Enter a file path.", "warn");
        return;
      }
      const name = fileNameInput.value.trim();
      setStatus("Ingesting...");
      const payload = await api("/ingest-file", {
        method: "POST",
        body: JSON.stringify(withSelectedFolder({ path, name: name || undefined }))
      });
      setStatus(`Ingested ${payload.doc_id}.`, "ok");
      await refreshDocuments();
    }

    async function reindexDocument(docId) {
      const path = fileInput.value.trim();
      if (!path) {
        setStatus("Enter a replacement file path.", "warn");
        return;
      }
      const name = fileNameInput.value.trim();
      setStatus("Reindexing...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}`, {
        method: "PUT",
        body: JSON.stringify(withSelectedFolder({ path, name: name || undefined }))
      });
      if (!payload.updated) {
        setStatus("Document not found.", "warn");
        return;
      }
      setStatus(`Reindexed ${payload.document.id}.`, "ok");
      await refreshDocuments();
    }

    async function renameDocument(docId, currentName) {
      const name = window.prompt("Rename document", currentName || "");
      if (name === null) {
        setStatus("Document rename cancelled.", "warn");
        return;
      }
      const trimmed = name.trim();
      if (!trimmed) {
        setStatus("Document name required.", "warn");
        return;
      }
      setStatus("Renaming document...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}/rename`, {
        method: "POST",
        body: JSON.stringify({ name: trimmed })
      });
      setStatus(payload.updated ? "Document renamed." : "Document not found.", payload.updated ? "ok" : "warn");
      await refreshDocuments();
    }

    async function moveDocument(docId) {
      const folderId = selectedFolderId();
      setStatus(folderId ? "Moving document..." : "Moving document to root...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}/move`, {
        method: "POST",
        body: JSON.stringify(folderId ? { folder_id: folderId } : {})
      });
      setStatus(payload.updated ? "Document moved." : "Document not found.", payload.updated ? "ok" : "warn");
      await refreshDocuments();
    }

    async function reindexDocumentUpload(docId) {
      const file = uploadInput.files && uploadInput.files[0];
      if (!file) {
        setStatus("Choose a replacement file.", "warn");
        return;
      }
      const name = fileNameInput.value.trim() || file.name;
      const form = new FormData();
      form.append("file", file);
      form.append("name", name);
      const folderId = selectedFolderId();
      if (folderId) {
        form.append("folder_id", folderId);
      }
      setStatus("Reindexing upload...");
      const response = await fetch(`/documents/${encodeURIComponent(docId)}/reindex-upload`, {
        method: "POST",
        headers: authHeaders(),
        body: form
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || response.statusText);
      }
      if (!payload.updated) {
        setStatus("Document not found.", "warn");
        return;
      }
      setStatus(`Reindexed ${payload.document.id}.`, "ok");
      await refreshDocuments();
    }

    async function downloadDocument(docId) {
      setStatus("Preparing document download...");
      const response = await fetch(`/documents/${encodeURIComponent(docId)}/download`, {
        headers: authHeaders()
      });
      if (!response.ok) {
        const text = await response.text();
        try {
          const payload = JSON.parse(text);
          throw new Error(payload.error || response.statusText);
        } catch (error) {
          if (error instanceof SyntaxError) {
            throw new Error(response.statusText);
          }
          throw error;
        }
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filenameFromDisposition(response.headers.get("Content-Disposition"), "pageindex-document.bin");
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 0);
      setStatus(`Document download prepared (${blob.size} bytes).`, "ok");
    }

    async function deleteDocument(docId) {
      if (!window.confirm("Permanently delete this document?")) {
        setStatus("Document delete cancelled.", "warn");
        return;
      }
      setStatus("Deleting document...");
      const payload = await api(`/documents/${encodeURIComponent(docId)}`, {
        method: "DELETE"
      });
      setStatus(payload.deleted ? "Document deleted." : "Document not found.", payload.deleted ? "ok" : "warn");
      await refreshDocuments();
    }

    async function uploadFile() {
      const files = Array.from(uploadInput.files || []);
      if (!files.length) {
        setStatus("Choose one or more files.", "warn");
        return;
      }
      const form = new FormData();
      files.forEach((file) => form.append("file", file));
      const folderId = selectedFolderId();
      if (folderId) {
        form.append("folder_id", folderId);
      }
      setStatus(files.length === 1 ? "Uploading..." : `Uploading ${files.length} files...`);
      const response = await fetch(files.length === 1 ? "/upload-file" : "/upload-files", {
        method: "POST",
        headers: authHeaders(),
        body: form
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || response.statusText);
      }
      const uploaded = payload.documents ? payload.documents.length : (payload.doc_id ? 1 : 0);
      const failed = payload.errors ? payload.errors.length : 0;
      setStatus(failed ? `Uploaded ${uploaded}, failed ${failed}.` : `Uploaded ${uploaded}.`, failed ? "warn" : "ok");
      await refreshDocuments();
    }

    async function queryCorpus() {
      setStatus("Querying...");
      const hint = hintInput.value.trim();
      const body = { query: queryInput.value.trim(), expert_hints: hint ? [hint] : [] };
      const scopedDocIds = activeQueryDocs.map((doc) => doc.id);
      if (activeQuerySourceSetId) {
        body.source_set_id = activeQuerySourceSetId;
      } else if (scopedDocIds.length) {
        body.doc_ids = scopedDocIds;
      }
      const payload = await api("/query", {
        method: "POST",
        body: JSON.stringify(body)
      });
      answerText.className = "";
      answerText.textContent = payload.answer || "No answer returned.";
      renderCitations(payload.citations || []);
      traceText.textContent = JSON.stringify(payload.trace || {}, null, 2);
      setStatus(payload.verification && payload.verification.ok ? "Trace verified." : "Trace returned warnings.", payload.verification && payload.verification.ok ? "ok" : "warn");
    }

    function queryRunQueryString(options = {}) {
      const params = new URLSearchParams();
      params.set("limit", options.limit || "25");
      const actor = queryRunActorFilterInput.value.trim();
      const query = queryRunSearchInput.value.trim();
      const since = queryRunSinceInput.value.trim();
      const until = queryRunUntilInput.value.trim();
      if (actor) {
        params.set("actor_user_id", actor);
      }
      if (query) {
        params.set("query", query);
      }
      if (since) {
        params.set("since", since);
      }
      if (until) {
        params.set("until", until);
      }
      if (options.format) {
        params.set("format", options.format);
      }
      return `?${params.toString()}`;
    }

    async function refreshQueryRuns() {
      setStatus("Refreshing query runs...");
      const payload = await api(`/query-runs${queryRunQueryString({ limit: "25" })}`);
      renderQueryRuns(payload.runs || []);
      setStatus("Query runs refreshed.", "ok");
    }

    async function exportQueryRuns() {
      setStatus("Exporting query runs...");
      const response = await fetch(`/query-runs/export${queryRunQueryString({ limit: "100", format: queryRunExportFormatInput.value || "jsonl" })}`, {
        headers: authHeaders()
      });
      const text = await response.text();
      if (!response.ok) {
        try {
          const payload = JSON.parse(text);
          throw new Error(payload.error || response.statusText);
        } catch (error) {
          if (error instanceof SyntaxError) {
            throw new Error(response.statusText);
          }
          throw error;
        }
      }
      queryRunExportText.value = text;
      setStatus("Query runs exported.", "ok");
    }

    async function refreshQueryRetention(options = {}) {
      if (!options.quiet) {
        setStatus("Refreshing query retention...");
      }
      const policy = await api("/query-retention");
      renderQueryRetention(policy);
      if (!options.quiet) {
        setStatus("Query retention refreshed.", "ok");
      }
    }

    function parsedQueryRetentionDays() {
      const value = queryRetentionDaysInput.value.trim();
      if (!value) {
        setStatus("Enter query retention days.", "warn");
        return null;
      }
      const days = Number(value);
      if (!Number.isInteger(days) || days <= 0) {
        setStatus("Query retention days must be a positive integer.", "warn");
        return null;
      }
      return days;
    }

    async function saveQueryRetention() {
      const days = parsedQueryRetentionDays();
      if (days == null) {
        return;
      }
      setStatus("Saving query retention...");
      const policy = await api("/query-retention", {
        method: "POST",
        body: JSON.stringify({ retention_days: days })
      });
      renderQueryRetention(policy);
      setStatus("Query retention saved.", "ok");
    }

    async function clearQueryRetention() {
      setStatus("Clearing query retention...");
      const policy = await api("/query-retention", {
        method: "POST",
        body: JSON.stringify({ clear: true })
      });
      renderQueryRetention(policy);
      setStatus("Query retention cleared.", "ok");
    }

    async function setQueryLegalHold(enabled) {
      setStatus(enabled ? "Enabling query legal hold..." : "Releasing query legal hold...");
      const reason = queryLegalHoldReasonInput.value.trim();
      const body = enabled && reason ? { legal_hold: true, legal_hold_reason: reason } : { legal_hold: enabled };
      const policy = await api("/query-retention", {
        method: "POST",
        body: JSON.stringify(body)
      });
      renderQueryRetention(policy);
      setStatus(enabled ? "Query legal hold enabled." : "Query legal hold released.", "ok");
    }

    async function previewQueryPurge() {
      setStatus("Previewing query purge...");
      const result = await api("/query-retention/purge", {
        method: "POST",
        body: JSON.stringify({ dry_run: true })
      });
      renderQueryPurgeResult(result);
      setStatus("Query purge previewed.", "ok");
    }

    async function purgeQueryRuns() {
      if (!window.confirm("Permanently purge query runs older than the retention policy?")) {
        setStatus("Query purge cancelled.", "warn");
        return;
      }
      setStatus("Purging query runs...");
      const result = await api("/query-retention/purge", {
        method: "POST",
        body: JSON.stringify({})
      });
      renderQueryPurgeResult(result);
      await refreshQueryRuns();
      setStatus("Query runs purged.", "ok");
    }

    async function loadQueryRunTrace(runId) {
      if (!runId) {
        setStatus("Query run not found.", "warn");
        return;
      }
      setStatus("Loading query trace...");
      const payload = await api(`/query-runs/${encodeURIComponent(runId)}`);
      traceText.textContent = JSON.stringify(payload.trace || {}, null, 2);
      setStatus("Query trace loaded.", "ok");
    }

    async function deleteQueryRun(runId) {
      if (!runId) {
        setStatus("Query run not found.", "warn");
        return;
      }
      if (!window.confirm("Permanently delete this query run and its trace rows?")) {
        setStatus("Query run delete cancelled.", "warn");
        return;
      }
      setStatus("Deleting query run...");
      const result = await api(`/query-runs/${encodeURIComponent(runId)}`, {
        method: "DELETE"
      });
      await refreshQueryRuns();
      setStatus(result.deleted ? "Query run deleted." : "Query run not found.", result.deleted ? "ok" : "warn");
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    document.getElementById("refreshButton").addEventListener("click", () => refreshAll().catch((error) => setStatus(error.message, "error")));
    document.getElementById("folderSelect").addEventListener("change", () => {
      activeFolderId = selectedFolderId();
      renderFolders(currentFolders, activeFolderId);
      setStatus(activeFolderId ? "Folder selected." : "No folder selected.", "ok");
    });
    document.getElementById("createFolderButton").addEventListener("click", () => createFolder().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshFoldersButton").addEventListener("click", () => refreshFolders().catch((error) => setStatus(error.message, "error")));
    document.getElementById("loadFolderAccessButton").addEventListener("click", () => loadFolderAccess().catch((error) => setStatus(error.message, "error")));
    document.getElementById("grantFolderAccessButton").addEventListener("click", () => grantFolderAccess().catch((error) => setStatus(error.message, "error")));
    document.getElementById("revokeFolderAccessButton").addEventListener("click", () => revokeFolderAccess().catch((error) => setStatus(error.message, "error")));
    document.getElementById("grantFolderGroupAccessButton").addEventListener("click", () => grantFolderGroupAccess().catch((error) => setStatus(error.message, "error")));
    document.getElementById("revokeFolderGroupAccessButton").addEventListener("click", () => revokeFolderGroupAccess().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshVirtualNodesButton").addEventListener("click", () => refreshVirtualNodes().catch((error) => setStatus(error.message, "error")));
    document.getElementById("planVirtualNodesButton").addEventListener("click", () => planVirtualNodes().catch((error) => setStatus(error.message, "error")));
    document.getElementById("uploadButton").addEventListener("click", () => uploadFile().catch((error) => setStatus(error.message, "error")));
    document.getElementById("ingestButton").addEventListener("click", () => ingestFile().catch((error) => setStatus(error.message, "error")));
    document.getElementById("importButton").addEventListener("click", () => importStructure().catch((error) => setStatus(error.message, "error")));
    document.getElementById("queryButton").addEventListener("click", () => queryCorpus().catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearQueryScopeButton").addEventListener("click", () => clearQueryScope());
    document.getElementById("refreshSourceSetsButton").addEventListener("click", () => refreshQuerySourceSets().catch((error) => setStatus(error.message, "error")));
    saveSourceSetButton.addEventListener("click", () => saveQuerySourceSet().catch((error) => setStatus(error.message, "error")));
    cancelSourceSetEditButton.addEventListener("click", () => cancelQuerySourceSetEdit());
    document.getElementById("refreshQueryRunsButton").addEventListener("click", () => refreshQueryRuns().catch((error) => setStatus(error.message, "error")));
    document.getElementById("exportQueryRunsButton").addEventListener("click", () => exportQueryRuns().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshQueryRetentionButton").addEventListener("click", () => refreshQueryRetention().catch((error) => setStatus(error.message, "error")));
    document.getElementById("saveQueryRetentionButton").addEventListener("click", () => saveQueryRetention().catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearQueryRetentionButton").addEventListener("click", () => clearQueryRetention().catch((error) => setStatus(error.message, "error")));
    document.getElementById("enableQueryLegalHoldButton").addEventListener("click", () => setQueryLegalHold(true).catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearQueryLegalHoldButton").addEventListener("click", () => setQueryLegalHold(false).catch((error) => setStatus(error.message, "error")));
    document.getElementById("previewQueryPurgeButton").addEventListener("click", () => previewQueryPurge().catch((error) => setStatus(error.message, "error")));
    document.getElementById("purgeQueryRunsButton").addEventListener("click", () => purgeQueryRuns().catch((error) => setStatus(error.message, "error")));
    document.getElementById("createConversationButton").addEventListener("click", () => createConversation().catch((error) => setStatus(error.message, "error")));
    document.getElementById("exportConversationButton").addEventListener("click", () => exportConversation().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshConversationsButton").addEventListener("click", () => refreshConversations().catch((error) => setStatus(error.message, "error")));
    conversationIncludeArchivedInput.addEventListener("change", () => refreshConversations().catch((error) => setStatus(error.message, "error")));
    document.getElementById("saveMemberButton").addEventListener("click", () => saveMember().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshMembersButton").addEventListener("click", () => refreshMembers().catch((error) => setStatus(error.message, "error")));
    document.getElementById("createGroupButton").addEventListener("click", () => createGroup().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshGroupsButton").addEventListener("click", () => refreshGroups().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshUsageButton").addEventListener("click", () => refreshUsage().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshQuotaPolicyButton").addEventListener("click", () => refreshWorkspaceQuotaPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("saveQuotaPolicyButton").addEventListener("click", () => saveWorkspaceQuotaPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearQuotaPolicyButton").addEventListener("click", () => clearWorkspaceQuotaPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("createInvitationButton").addEventListener("click", () => createInvitation().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshInvitationsButton").addEventListener("click", () => refreshInvitations().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshTokensButton").addEventListener("click", () => refreshApiTokens().catch((error) => setStatus(error.message, "error")));
    document.getElementById("createTokenButton").addEventListener("click", () => createApiToken().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshTokenPolicyButton").addEventListener("click", () => refreshApiTokenPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("saveTokenPolicyButton").addEventListener("click", () => saveApiTokenPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearTokenPolicyButton").addEventListener("click", () => clearApiTokenPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshAuditButton").addEventListener("click", () => refreshAuditEvents().catch((error) => setStatus(error.message, "error")));
    document.getElementById("exportAuditButton").addEventListener("click", () => exportAuditEvents().catch((error) => setStatus(error.message, "error")));
    document.getElementById("verifyAuditIntegrityButton").addEventListener("click", () => verifyAuditIntegrity().catch((error) => setStatus(error.message, "error")));
    document.getElementById("exportWorkspaceButton").addEventListener("click", () => exportWorkspaceBundle().catch((error) => setStatus(error.message, "error")));
    document.getElementById("previewWorkspaceImportButton").addEventListener("click", () => previewWorkspaceImport().catch((error) => setStatus(error.message, "error")));
    document.getElementById("restoreWorkspaceImportButton").addEventListener("click", () => restoreWorkspaceImport().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshAuditRetentionButton").addEventListener("click", () => refreshAuditRetention().catch((error) => setStatus(error.message, "error")));
    document.getElementById("saveAuditRetentionButton").addEventListener("click", () => saveAuditRetention().catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearAuditRetentionButton").addEventListener("click", () => clearAuditRetention().catch((error) => setStatus(error.message, "error")));
    document.getElementById("enableAuditLegalHoldButton").addEventListener("click", () => setAuditLegalHold(true).catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearAuditLegalHoldButton").addEventListener("click", () => setAuditLegalHold(false).catch((error) => setStatus(error.message, "error")));
    document.getElementById("previewAuditPurgeButton").addEventListener("click", () => previewAuditPurge().catch((error) => setStatus(error.message, "error")));
    document.getElementById("purgeAuditButton").addEventListener("click", () => purgeAuditEvents().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshReadinessButton").addEventListener("click", () => refreshDeploymentReadiness().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshProviderButton").addEventListener("click", () => refreshProviderConfig().catch((error) => {
      renderProviderConfig(null);
      providerConfigSummary.textContent = "Provider unavailable.";
      setStatus(error.message, "error");
    }));
    document.getElementById("saveProviderButton").addEventListener("click", () => saveProviderConfig().catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearProviderButton").addEventListener("click", () => clearProviderConfig().catch((error) => setStatus(error.message, "error")));
    document.getElementById("chatButton").addEventListener("click", () => sendChatMessage().catch((error) => setStatus(error.message, "error")));
    applyQueryPrefillFromLocation();
  </script>
</body>
</html>
"""
