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
    .member-list,
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
              <input id="uploadInput" type="file" aria-label="Upload file">
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
              <button id="refreshConversationsButton" class="secondary" type="button">Refresh chats</button>
              <div id="conversationList" class="conversation-list muted">No conversations loaded.</div>
              <textarea id="conversationExportText" readonly placeholder="conversation export output" aria-label="Conversation export output"></textarea>
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
              <div class="import-row">
                <select id="auditFormatInput" aria-label="Audit export format">
                  <option value="jsonl">jsonl</option>
                  <option value="csv">csv</option>
                </select>
                <button id="refreshAuditButton" class="secondary" type="button">Refresh</button>
              </div>
              <button id="exportAuditButton" class="secondary" type="button">Export audit</button>
              <div class="import-row">
                <input id="auditRetentionDaysInput" value="" placeholder="retention days" aria-label="Audit retention days">
                <button id="saveAuditRetentionButton" type="button">Save</button>
              </div>
              <div class="provider-actions">
                <button id="refreshAuditRetentionButton" class="secondary" type="button">Policy</button>
                <button id="previewAuditPurgeButton" class="secondary" type="button">Preview</button>
                <button id="purgeAuditButton" class="secondary" type="button">Purge</button>
              </div>
              <button id="clearAuditRetentionButton" class="secondary" type="button">Clear retention</button>
              <div id="auditRetentionSummary" class="muted">Retention not loaded.</div>
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
              <button id="previewWorkspaceImportButton" class="secondary" type="button">Preview import</button>
              <div id="workspaceImportSummary" class="muted">No import preview loaded.</div>
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
            <h2 class="section-title">Documents</h2>
            <div id="documentList" class="doc-list muted">No documents loaded.</div>
            <div id="documentAccessPanel" class="muted" style="margin-top:12px">No document access loaded.</div>
            <div id="versionList" class="version-list muted" style="margin-top:12px">No versions loaded.</div>
            <div id="pagePreviewList" class="page-list muted" style="margin-top:12px">No pages loaded.</div>
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
    const conversationExportFormatInput = document.getElementById("conversationExportFormatInput");
    const conversationExportText = document.getElementById("conversationExportText");
    const memberUserInput = document.getElementById("memberUserInput");
    const memberRoleInput = document.getElementById("memberRoleInput");
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
    const auditFormatInput = document.getElementById("auditFormatInput");
    const auditExportText = document.getElementById("auditExportText");
    const auditRetentionDaysInput = document.getElementById("auditRetentionDaysInput");
    const auditRetentionSummary = document.getElementById("auditRetentionSummary");
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
    const hintInput = document.getElementById("hintInput");
    const chatInput = document.getElementById("chatInput");
    const statusEl = document.getElementById("status");
    const documentList = document.getElementById("documentList");
    const documentAccessPanel = document.getElementById("documentAccessPanel");
    const versionList = document.getElementById("versionList");
    const pagePreviewList = document.getElementById("pagePreviewList");
    const folderList = document.getElementById("folderList");
    const virtualNodeList = document.getElementById("virtualNodeList");
    const conversationList = document.getElementById("conversationList");
    const memberList = document.getElementById("memberList");
    const invitationList = document.getElementById("invitationList");
    const tokenList = document.getElementById("tokenList");
    const auditList = document.getElementById("auditList");
    const providerConfigSummary = document.getElementById("providerConfigSummary");
    const messageList = document.getElementById("messageList");
    const answerText = document.getElementById("answerText");
    const citationList = document.getElementById("citationList");
    const traceText = document.getElementById("traceText");
    let activeConversationId = "";
    let activeFolderId = "";
    let workspaceExportUrl = "";
    let currentFolders = [];

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
            <button class="secondary" type="button" data-pages-doc-id="${escapeHtml(doc.id)}">Preview</button>
            <button class="secondary" type="button" data-versions-doc-id="${escapeHtml(doc.id)}">Versions</button>
            <button class="secondary" type="button" data-access-doc-id="${escapeHtml(doc.id)}">Access</button>
            <button class="secondary" type="button" data-reindex-doc-id="${escapeHtml(doc.id)}">Reindex</button>
          </div>
        </article>
      `).join("");
      documentList.querySelectorAll("[data-pages-doc-id]").forEach((button) => {
        button.addEventListener("click", () => loadDocumentPages(button.dataset.pagesDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-versions-doc-id]").forEach((button) => {
        button.addEventListener("click", () => loadDocumentVersions(button.dataset.versionsDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-access-doc-id]").forEach((button) => {
        button.addEventListener("click", () => loadDocumentAccess(button.dataset.accessDocId).catch((error) => setStatus(error.message, "error")));
      });
      documentList.querySelectorAll("[data-reindex-doc-id]").forEach((button) => {
        button.addEventListener("click", () => reindexDocument(button.dataset.reindexDocId).catch((error) => setStatus(error.message, "error")));
      });
    }

    function renderDocumentAccess(docId, access) {
      if (!access) {
        documentAccessPanel.className = "muted";
        documentAccessPanel.textContent = "No document access loaded.";
        return;
      }
      const grants = access.grants || [];
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
            <button id="grantDocumentAccessButton" type="button">Grant</button>
            <button id="revokeDocumentAccessButton" class="secondary" type="button">Revoke</button>
          </div>
        </article>
        <div class="member-list">${grantsHtml}</div>
      `;
      document.getElementById("saveDocumentAccessModeButton").addEventListener("click", () => saveDocumentAccessMode(docId).catch((error) => setStatus(error.message, "error")));
      document.getElementById("grantDocumentAccessButton").addEventListener("click", () => grantDocumentAccess(docId).catch((error) => setStatus(error.message, "error")));
      document.getElementById("revokeDocumentAccessButton").addEventListener("click", () => revokeDocumentAccess(docId).catch((error) => setStatus(error.message, "error")));
      documentAccessPanel.querySelectorAll("[data-revoke-access-doc-id]").forEach((button) => {
        button.addEventListener("click", () => revokeDocumentAccess(button.dataset.revokeAccessDocId, button.dataset.revokeAccessUserId).catch((error) => setStatus(error.message, "error")));
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
        <button class="folder ${folder.id === activeFolderId ? "active" : "secondary"}" type="button" data-folder-id="${escapeHtml(folder.id)}">
          <strong>${escapeHtml(folder.name)}</strong>
          <div class="muted">${escapeHtml(folder.path)}</div>
        </button>
      `).join("");
      folderList.querySelectorAll("[data-folder-id]").forEach((button) => {
        button.addEventListener("click", () => {
          activeFolderId = button.dataset.folderId || "";
          folderSelect.value = activeFolderId;
          renderFolders(folders, activeFolderId);
          const selected = folders.find((folder) => folder.id === activeFolderId);
          setStatus(selected ? `Folder selected ${selected.path}.` : "No folder selected.", "ok");
        });
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

    function renderConversations(conversations) {
      if (!conversations.length) {
        conversationList.className = "conversation-list muted";
        conversationList.textContent = "No conversations loaded.";
        return;
      }
      conversationList.className = "conversation-list";
      conversationList.innerHTML = conversations.map((conversation) => `
        <button class="conversation ${conversation.id === activeConversationId ? "active" : "secondary"}" type="button" data-conversation-id="${escapeHtml(conversation.id)}">
          <strong>${escapeHtml(conversation.title)}</strong>
          <div class="muted">${escapeHtml(conversation.message_count || 0)} messages</div>
        </button>
      `).join("");
      conversationList.querySelectorAll("[data-conversation-id]").forEach((button) => {
        button.addEventListener("click", () => selectConversation(button.dataset.conversationId));
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
      if (!policy || policy.retention_days == null) {
        auditRetentionDaysInput.value = "";
        auditRetentionSummary.className = "muted";
        auditRetentionSummary.textContent = "Retention not set.";
        return;
      }
      auditRetentionDaysInput.value = String(policy.retention_days);
      auditRetentionSummary.className = "muted";
      auditRetentionSummary.textContent = `${policy.retention_days} days | updated ${policy.updated_at || "unknown"}`;
    }

    function renderAuditPurgeResult(result) {
      const action = result.dry_run ? "Preview" : "Purge";
      auditRetentionSummary.className = result.purged > 0 ? "status warn" : "muted";
      auditRetentionSummary.textContent = `${action}: matched ${result.matched}, purged ${result.purged}`;
    }

    function renderWorkspaceImportPreview(report) {
      const errors = Array.isArray(report.errors) ? report.errors.length : 0;
      const warnings = Array.isArray(report.warnings) ? report.warnings.length : 0;
      const tables = report.table_counts || {};
      const tableTotal = Object.keys(tables).length;
      const docs = tables.documents == null ? 0 : tables.documents;
      workspaceImportSummary.className = report.ok ? "status ok" : "status error";
      workspaceImportSummary.textContent = `${report.ok ? "Preview ok" : "Preview failed"}: ${tableTotal} tables, ${docs} documents, ${errors} errors, ${warnings} warnings`;
      workspaceImportReportText.textContent = JSON.stringify(report, null, 2);
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
      renderDocuments(payload.documents || []);
      setStatus("Documents refreshed.", "ok");
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
      const userId = input.value.trim();
      if (!userId) {
        setStatus("Enter a user id.", "warn");
        return;
      }
      await updateDocumentAccess(docId, { grant_user_id: userId }, "Document access granted.");
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
      const payload = await api("/conversations");
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
      if (action) {
        params.set("action", action);
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
      await refreshConversations();
      try {
        await refreshMembers();
      } catch (error) {
        memberList.className = "member-list muted";
        memberList.textContent = "Team unavailable.";
        setStatus("Documents and chats refreshed.", "ok");
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

    async function createConversation() {
      const title = conversationTitleInput.value.trim();
      setStatus("Creating chat...");
      const conversation = await api("/conversations", {
        method: "POST",
        body: JSON.stringify({ title: title || undefined })
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

    function filenameFromDisposition(value) {
      const match = /filename="([^"]+)"/.exec(value || "");
      return match ? match[1] : "pageindex-workspace-export.zip";
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

    async function uploadFile() {
      const file = uploadInput.files && uploadInput.files[0];
      if (!file) {
        setStatus("Choose a file.", "warn");
        return;
      }
      const form = new FormData();
      form.append("file", file);
      form.append("name", file.name);
      const folderId = selectedFolderId();
      if (folderId) {
        form.append("folder_id", folderId);
      }
      setStatus("Uploading...");
      const response = await fetch("/upload-file", {
        method: "POST",
        headers: authHeaders(),
        body: form
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || response.statusText);
      }
      setStatus(`Uploaded ${payload.doc_id}.`, "ok");
      await refreshDocuments();
    }

    async function queryCorpus() {
      setStatus("Querying...");
      const hint = hintInput.value.trim();
      const payload = await api("/query", {
        method: "POST",
        body: JSON.stringify({ query: queryInput.value.trim(), expert_hints: hint ? [hint] : [] })
      });
      answerText.className = "";
      answerText.textContent = payload.answer || "No answer returned.";
      renderCitations(payload.citations || []);
      traceText.textContent = JSON.stringify(payload.trace || {}, null, 2);
      setStatus(payload.verification && payload.verification.ok ? "Trace verified." : "Trace returned warnings.", payload.verification && payload.verification.ok ? "ok" : "warn");
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
    document.getElementById("refreshVirtualNodesButton").addEventListener("click", () => refreshVirtualNodes().catch((error) => setStatus(error.message, "error")));
    document.getElementById("planVirtualNodesButton").addEventListener("click", () => planVirtualNodes().catch((error) => setStatus(error.message, "error")));
    document.getElementById("uploadButton").addEventListener("click", () => uploadFile().catch((error) => setStatus(error.message, "error")));
    document.getElementById("ingestButton").addEventListener("click", () => ingestFile().catch((error) => setStatus(error.message, "error")));
    document.getElementById("importButton").addEventListener("click", () => importStructure().catch((error) => setStatus(error.message, "error")));
    document.getElementById("queryButton").addEventListener("click", () => queryCorpus().catch((error) => setStatus(error.message, "error")));
    document.getElementById("createConversationButton").addEventListener("click", () => createConversation().catch((error) => setStatus(error.message, "error")));
    document.getElementById("exportConversationButton").addEventListener("click", () => exportConversation().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshConversationsButton").addEventListener("click", () => refreshConversations().catch((error) => setStatus(error.message, "error")));
    document.getElementById("saveMemberButton").addEventListener("click", () => saveMember().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshMembersButton").addEventListener("click", () => refreshMembers().catch((error) => setStatus(error.message, "error")));
    document.getElementById("createInvitationButton").addEventListener("click", () => createInvitation().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshInvitationsButton").addEventListener("click", () => refreshInvitations().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshTokensButton").addEventListener("click", () => refreshApiTokens().catch((error) => setStatus(error.message, "error")));
    document.getElementById("createTokenButton").addEventListener("click", () => createApiToken().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshTokenPolicyButton").addEventListener("click", () => refreshApiTokenPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("saveTokenPolicyButton").addEventListener("click", () => saveApiTokenPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearTokenPolicyButton").addEventListener("click", () => clearApiTokenPolicy().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshAuditButton").addEventListener("click", () => refreshAuditEvents().catch((error) => setStatus(error.message, "error")));
    document.getElementById("exportAuditButton").addEventListener("click", () => exportAuditEvents().catch((error) => setStatus(error.message, "error")));
    document.getElementById("exportWorkspaceButton").addEventListener("click", () => exportWorkspaceBundle().catch((error) => setStatus(error.message, "error")));
    document.getElementById("previewWorkspaceImportButton").addEventListener("click", () => previewWorkspaceImport().catch((error) => setStatus(error.message, "error")));
    document.getElementById("refreshAuditRetentionButton").addEventListener("click", () => refreshAuditRetention().catch((error) => setStatus(error.message, "error")));
    document.getElementById("saveAuditRetentionButton").addEventListener("click", () => saveAuditRetention().catch((error) => setStatus(error.message, "error")));
    document.getElementById("clearAuditRetentionButton").addEventListener("click", () => clearAuditRetention().catch((error) => setStatus(error.message, "error")));
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
  </script>
</body>
</html>
"""
