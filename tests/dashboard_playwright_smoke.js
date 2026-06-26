const { chromium } = require("playwright");

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function waitForText(page, selector, expected) {
  await page.waitForFunction(
    ({ selector, expected }) => document.querySelector(selector)?.textContent.includes(expected),
    { selector, expected }
  );
}

async function waitForAnyText(page, selector, expectedValues) {
  await page.waitForFunction(
    ({ selector, expectedValues }) => {
      const text = document.querySelector(selector)?.textContent || "";
      return expectedValues.some((expected) => text.includes(expected));
    },
    { selector, expectedValues }
  );
}

(async () => {
  const baseUrl = requiredEnv("PAGEINDEX_DASHBOARD_BASE_URL");
  const token = requiredEnv("PAGEINDEX_DASHBOARD_TOKEN");
  const expectedDocument = requiredEnv("PAGEINDEX_DASHBOARD_EXPECTED_DOCUMENT");
  const expectedAnswer = process.env.PAGEINDEX_DASHBOARD_EXPECTED_ANSWER || `Found relevant evidence in ${expectedDocument}`;
  const query = process.env.PAGEINDEX_DASHBOARD_QUERY || "browser evidence";
  const importPreviewPath = requiredEnv("PAGEINDEX_DASHBOARD_IMPORT_PREVIEW_PATH");
  const screenshotPath = process.env.PAGEINDEX_DASHBOARD_SCREENSHOT;
  const failures = [];

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(10000);
  page.on("pageerror", (error) => failures.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") {
      failures.push(`console: ${message.text()}`);
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      failures.push(`http ${response.status()}: ${response.url()}`);
    }
  });

  try {
    await page.goto(new URL("/dashboard", baseUrl).toString(), { waitUntil: "domcontentloaded" });
    await page.fill("#apiTokenInput", token);
    await page.click("#refreshButton");
    await waitForText(page, "#documentList", expectedDocument);
    await waitForAnyText(page, "#status", ["Team refreshed.", "Documents and chats refreshed."]);

    const versionsResponse = page.waitForResponse(
      (response) => response.url().includes("/documents/") && response.url().endsWith("/versions") && response.request().method() === "GET"
    );
    await page.locator("[data-versions-doc-id]").first().click();
    await versionsResponse;
    await waitForText(page, "#status", "Versions refreshed.");
    await waitForText(page, "#versionList", "document.ingest");

    const pagesResponse = page.waitForResponse(
      (response) => response.url().includes("/documents/") && response.url().endsWith("/pages?limit=5&max_chars=2000") && response.request().method() === "GET"
    );
    await page.locator("[data-pages-doc-id]").first().click();
    await pagesResponse;
    await waitForText(page, "#status", "Pages refreshed.");
    await waitForText(page, "#pagePreviewList", "Playwright browser evidence");

    const accessResponse = page.waitForResponse(
      (response) => response.url().includes("/documents/") && response.url().endsWith("/access") && response.request().method() === "GET"
    );
    await page.locator("[data-access-doc-id]").first().click();
    await accessResponse;
    await waitForText(page, "#status", "Access refreshed.");
    await waitForText(page, "#documentAccessPanel", "mode workspace");

    await page.selectOption("#documentAccessModeInput", "restricted");
    const saveAccessModeResponse = page.waitForResponse(
      (response) => response.url().includes("/documents/")
        && response.url().endsWith("/access")
        && response.request().method() === "POST"
        && (response.request().postData() || "").includes("access_mode")
    );
    await page.click("#saveDocumentAccessModeButton");
    await saveAccessModeResponse;
    await waitForText(page, "#status", "Access mode saved.");
    await waitForText(page, "#documentAccessPanel", "mode restricted");

    await page.fill("#documentAccessUserInput", "alice");
    const grantAccessResponse = page.waitForResponse(
      (response) => response.url().includes("/documents/")
        && response.url().endsWith("/access")
        && response.request().method() === "POST"
        && (response.request().postData() || "").includes("grant_user_id")
    );
    await page.click("#grantDocumentAccessButton");
    await grantAccessResponse;
    await waitForText(page, "#status", "Document access granted.");
    await waitForText(page, "#documentAccessPanel", "alice");

    const revokeAccessResponse = page.waitForResponse(
      (response) => response.url().includes("/documents/")
        && response.url().endsWith("/access")
        && response.request().method() === "POST"
        && (response.request().postData() || "").includes("revoke_user_id")
    );
    await page.locator("[data-revoke-access-user-id='alice']").click();
    await revokeAccessResponse;
    await waitForText(page, "#status", "Document access revoked.");
    await waitForText(page, "#documentAccessPanel", "No direct grants.");

    await waitForText(page, "#folderList", "No folders loaded.");

    await page.fill("#folderNameInput", "Browser");
    const createFolderResponse = page.waitForResponse(
      (response) => response.url().endsWith("/folders") && response.request().method() === "POST"
    );
    await page.click("#createFolderButton");
    await createFolderResponse;
    await waitForText(page, "#status", "Folder created.");
    await waitForText(page, "#folderList", "/Browser");
    const selectedFolderLabel = await page.locator("#folderSelect option:checked").textContent();
    assert(selectedFolderLabel && selectedFolderLabel.includes("/Browser"), "created folder was not selected");

    await waitForText(page, "#virtualNodeList", "/virtual/by-kind/txt");
    await page.fill("#virtualNodeQueryInput", "txt");
    const planVirtualNodesResponse = page.waitForResponse(
      (response) => response.url().includes("/virtual-nodes?") && response.request().method() === "GET"
    );
    await page.click("#planVirtualNodesButton");
    await planVirtualNodesResponse;
    await waitForText(page, "#status", "Virtual node plan refreshed.");
    await waitForText(page, "#virtualNodeList", "score");

    await page.fill("#conversationTitleInput", "Browser chat");
    const createConversationResponse = page.waitForResponse(
      (response) => response.url().endsWith("/conversations") && response.request().method() === "POST"
    );
    await page.click("#createConversationButton");
    await createConversationResponse;
    await waitForText(page, "#status", "Conversation created.");
    await waitForText(page, "#conversationList", "Browser chat");

    await page.fill("#chatInput", "browser evidence");
    const chatMessageResponse = page.waitForResponse(
      (response) => response.url().includes("/conversations/")
        && response.url().endsWith("/messages")
        && response.request().method() === "POST"
    );
    await page.click("#chatButton");
    await chatMessageResponse;
    await waitForText(page, "#status", "Conversation trace verified.");
    await waitForText(page, "#messageList", "browser evidence");

    await page.selectOption("#conversationExportFormatInput", "markdown");
    const exportConversationResponse = page.waitForResponse(
      (response) => response.url().includes("/conversations/")
        && response.url().includes("/export")
        && response.request().method() === "GET"
    );
    await page.click("#exportConversationButton");
    await exportConversationResponse;
    await waitForText(page, "#status", "Conversation exported.");
    const conversationExport = await page.inputValue("#conversationExportText");
    assert(conversationExport.includes("# Browser chat"), "conversation export did not include title");
    assert(conversationExport.includes("browser evidence"), "conversation export did not include user message");
    assert(conversationExport.includes("## Assistant"), "conversation export did not include assistant message");

    await waitForText(page, "#invitationList", "No invitations loaded.");
    await page.fill("#invitationEmailInput", "browser-invite@example.com");
    await page.fill("#invitationExpiresInDaysInput", "7");
    await page.selectOption("#invitationRoleInput", "viewer");
    const createInvitationResponse = page.waitForResponse(
      (response) => response.url().endsWith("/workspace-invitations") && response.request().method() === "POST"
    );
    await page.click("#createInvitationButton");
    await createInvitationResponse;
    await waitForText(page, "#status", "Invitation created.");
    await waitForText(page, "#invitationList", "browser-invite@example.com");
    await waitForText(page, "#invitationList", "pending");

    const revokeInvitationResponse = page.waitForResponse(
      (response) => response.url().includes("/workspace-invitations/") && response.request().method() === "DELETE"
    );
    await page.locator("[data-revoke-invitation-id]").first().click();
    await revokeInvitationResponse;
    await waitForText(page, "#status", "Invitation revoked.");
    await waitForText(page, "#invitationList", "revoked");

    await waitForText(page, "#tokenList", "browser");
    await page.fill("#tokenNameInput", "browser-child");
    await page.fill("#tokenExpiresInDaysInput", "7");
    const createTokenResponse = page.waitForResponse(
      (response) => response.url().endsWith("/api-tokens") && response.request().method() === "POST"
    );
    await page.click("#createTokenButton");
    await createTokenResponse;
    await waitForText(page, "#status", "Token created.");
    await waitForText(page, "#tokenList", "browser-child");
    const createdSecret = await page.inputValue("#tokenSecretOutput");
    assert(createdSecret.startsWith("pit_"), "created token secret was not shown once");

    const childTokenCard = page.locator('[data-token-name="browser-child"]').first();
    const rotateTokenResponse = page.waitForResponse(
      (response) => response.url().includes("/api-tokens/") && response.url().endsWith("/rotate") && response.request().method() === "POST"
    );
    await childTokenCard.locator("[data-rotate-token-id]").click();
    await rotateTokenResponse;
    await waitForText(page, "#status", "Token rotated.");
    await waitForText(page, "#tokenList", "browser-child");
    const rotatedSecret = await page.inputValue("#tokenSecretOutput");
    assert(rotatedSecret.startsWith("pit_"), "rotated token secret was not shown once");
    assert(rotatedSecret !== createdSecret, "rotated token secret did not change");

    const rotatedTokenCard = page.locator('[data-token-name="browser-child"]').first();
    const revokeTokenResponse = page.waitForResponse(
      (response) => response.url().includes("/api-tokens/") && response.request().method() === "DELETE"
    );
    await rotatedTokenCard.locator("[data-revoke-token-id]").click();
    await revokeTokenResponse;
    await waitForText(page, "#status", "Token revoked.");
    await page.waitForFunction(
      () => !(document.querySelector("#tokenList")?.textContent || "").includes("browser-child")
    );

    await waitForText(page, "#tokenPolicySummary", "Policy not set.");
    await page.fill("#tokenPolicyDefaultExpirationInput", "9");
    await page.fill("#tokenPolicyRotationDueInput", "21");
    const saveTokenPolicyResponse = page.waitForResponse(
      (response) => response.url().endsWith("/api-token-policy") && response.request().method() === "POST"
    );
    await page.click("#saveTokenPolicyButton");
    await saveTokenPolicyResponse;
    await waitForText(page, "#status", "Token policy saved.");
    await waitForText(page, "#tokenPolicySummary", "default 9 days");
    await waitForText(page, "#tokenPolicySummary", "rotation 21 days");

    const refreshTokenPolicyResponse = page.waitForResponse(
      (response) => response.url().endsWith("/api-token-policy") && response.request().method() === "GET"
    );
    await page.click("#refreshTokenPolicyButton");
    await refreshTokenPolicyResponse;
    await waitForText(page, "#status", "Token policy refreshed.");
    await waitForText(page, "#tokenPolicySummary", "default 9 days");

    const clearTokenPolicyResponse = page.waitForResponse(
      (response) => response.url().endsWith("/api-token-policy") && response.request().method() === "POST"
    );
    await page.click("#clearTokenPolicyButton");
    await clearTokenPolicyResponse;
    await waitForText(page, "#status", "Token policy cleared.");
    await waitForText(page, "#tokenPolicySummary", "Policy not set.");

    await page.fill("#auditActionInput", "api_token.create");
    const refreshAuditResponse = page.waitForResponse(
      (response) => response.url().includes("/audit-events?") && !response.url().includes("/export") && response.request().method() === "GET"
    );
    await page.click("#refreshAuditButton");
    await refreshAuditResponse;
    await waitForText(page, "#status", "Audit refreshed.");
    await waitForText(page, "#auditList", "api_token.create");
    await waitForText(page, "#auditList", "browser-child");

    const exportAuditResponse = page.waitForResponse(
      (response) => response.url().includes("/audit-events/export") && response.request().method() === "GET"
    );
    await page.click("#exportAuditButton");
    await exportAuditResponse;
    await waitForText(page, "#status", "Audit exported.");
    const auditExport = await page.inputValue("#auditExportText");
    assert(auditExport.includes("api_token.create"), "audit export did not include create event");
    assert(auditExport.includes("browser-child"), "audit export did not include child token metadata");
    assert(!auditExport.includes(createdSecret), "audit export leaked created token secret");
    assert(!auditExport.includes(rotatedSecret), "audit export leaked rotated token secret");

    const workspaceExportResponsePromise = page.waitForResponse(
      (response) => response.url().endsWith("/workspace-export") && response.request().method() === "GET"
    );
    await page.click("#exportWorkspaceButton");
    const workspaceExportResponse = await workspaceExportResponsePromise;
    const workspaceExportLength = Number(workspaceExportResponse.headers()["content-length"] || "0");
    await waitForText(page, "#status", "Workspace export prepared.");
    await waitForText(page, "#workspaceExportSummary", "workspace export ready");
    const workspaceExportSummary = (await page.textContent("#workspaceExportSummary")) || "";
    const workspaceExportDownload = await page.locator("#workspaceExportLink").getAttribute("download");
    assert(workspaceExportLength > 0, "workspace export response was empty");
    assert(!workspaceExportSummary.includes("(0 bytes)"), "workspace export summary reported zero bytes");
    assert(workspaceExportDownload && workspaceExportDownload.includes("workspace-export.zip"), "workspace export download filename was not set");

    await page.fill("#workspaceImportPathInput", importPreviewPath);
    const workspaceImportPreviewResponse = page.waitForResponse(
      (response) => response.url().endsWith("/workspace-import/preview") && response.request().method() === "POST"
    );
    await page.click("#previewWorkspaceImportButton");
    await workspaceImportPreviewResponse;
    await waitForText(page, "#status", "Import preview passed.");
    await waitForText(page, "#workspaceImportSummary", "Preview ok");
    const workspaceImportReport = JSON.parse((await page.textContent("#workspaceImportReportText")) || "{}");
    assert(workspaceImportReport.ok === true, "workspace import preview did not pass");
    assert(workspaceImportReport.table_counts?.documents === 1, "workspace import preview did not count documents");
    assert(!JSON.stringify(workspaceImportReport).includes("pit_"), "workspace import preview leaked token marker");

    await waitForText(page, "#auditRetentionSummary", "Retention not set.");
    await page.fill("#auditRetentionDaysInput", "1");
    const saveRetentionResponse = page.waitForResponse(
      (response) => response.url().endsWith("/audit-retention") && response.request().method() === "POST"
    );
    await page.click("#saveAuditRetentionButton");
    await saveRetentionResponse;
    await waitForText(page, "#status", "Retention saved.");
    await waitForText(page, "#auditRetentionSummary", "1 days");

    const previewPurgeResponse = page.waitForResponse(
      (response) => response.url().endsWith("/audit-retention/purge")
        && response.request().method() === "POST"
        && (response.request().postData() || "").includes("dry_run")
    );
    await page.click("#previewAuditPurgeButton");
    await previewPurgeResponse;
    await waitForText(page, "#status", "Retention previewed.");
    await waitForText(page, "#auditRetentionSummary", "matched 1, purged 0");

    page.once("dialog", async (dialog) => {
      await dialog.accept();
    });
    const purgeResponse = page.waitForResponse(
      (response) => response.url().endsWith("/audit-retention/purge")
        && response.request().method() === "POST"
        && !(response.request().postData() || "").includes("dry_run")
    );
    await page.click("#purgeAuditButton");
    await purgeResponse;
    await waitForText(page, "#status", "Audit purged.");
    await waitForText(page, "#auditRetentionSummary", "matched 1, purged 1");

    const clearRetentionResponse = page.waitForResponse(
      (response) => response.url().endsWith("/audit-retention") && response.request().method() === "POST"
    );
    await page.click("#clearAuditRetentionButton");
    await clearRetentionResponse;
    await waitForText(page, "#status", "Retention cleared.");
    await waitForText(page, "#auditRetentionSummary", "Retention not set.");

    const readinessResponse = page.waitForResponse(
      (response) => response.url().endsWith("/deployment-check") && response.request().method() === "GET"
    );
    await page.click("#refreshReadinessButton");
    await readinessResponse;
    await waitForText(page, "#status", "Readiness refreshed.");
    await waitForText(page, "#readinessSummary", "Ready:");
    const readinessReport = JSON.parse((await page.textContent("#readinessReportText")) || "{}");
    assert(readinessReport.ok === true, "deployment readiness report was not ready");
    assert(readinessReport.checks?.strict_http?.ok === true, "deployment readiness did not prove strict HTTP");
    assert(!JSON.stringify(readinessReport).includes("pit_"), "deployment readiness leaked token secret");

    await waitForText(page, "#providerConfigSummary", "Provider not configured.");

    await page.fill("#providerBaseUrlInput", "http://127.0.0.1:1/v1");
    await page.fill("#providerModelInput", "dashboard-provider-model");
    await page.fill("#providerApiKeyEnvVarInput", "PAGEINDEX_DASHBOARD_PROVIDER_KEY");
    await page.fill("#providerTimeoutInput", "2.5");
    const saveProviderResponse = page.waitForResponse(
      (response) => response.url().endsWith("/provider-config") && response.request().method() === "POST"
    );
    await page.click("#saveProviderButton");
    await saveProviderResponse;
    await waitForText(page, "#status", "Provider saved.");
    await waitForText(page, "#providerConfigSummary", "dashboard-provider-model");
    await waitForText(page, "#providerConfigSummary", "key env unset");

    const refreshProviderResponse = page.waitForResponse(
      (response) => response.url().endsWith("/provider-config") && response.request().method() === "GET"
    );
    await page.click("#refreshProviderButton");
    await refreshProviderResponse;
    await waitForText(page, "#status", "Provider refreshed.");
    await waitForText(page, "#providerConfigSummary", "dashboard-provider-model");

    const clearProviderResponse = page.waitForResponse(
      (response) => response.url().endsWith("/provider-config") && response.request().method() === "POST"
    );
    await page.click("#clearProviderButton");
    await clearProviderResponse;
    await waitForText(page, "#status", "Provider cleared.");
    await waitForText(page, "#providerConfigSummary", "Provider not configured.");

    await page.fill("#queryInput", query);
    await page.fill("#hintInput", "");
    const queryResponse = page.waitForResponse(
      (response) => response.url().endsWith("/query") && response.request().method() === "POST"
    );
    await page.click("#queryButton");
    await queryResponse;
    await waitForText(page, "#status", "Trace verified.");

    const answer = (await page.textContent("#answerText")) || "";
    const citations = (await page.textContent("#citationList")) || "";
    const traceText = (await page.textContent("#traceText")) || "{}";
    const trace = JSON.parse(traceText);

    assert(answer.includes(expectedAnswer), `answer panel did not include expected text: ${expectedAnswer}`);
    assert(citations.includes(expectedDocument), "citation panel did not render expected document");
    assert(trace.scope && trace.scope.query_tree, "trace did not include query tree scope");
    assert(trace.scope.hybrid_policy, "trace did not include hybrid policy scope");
    assert(Array.isArray(trace.evidence) && trace.evidence.length > 0, "trace did not include evidence");

    if (screenshotPath) {
      await page.screenshot({ path: screenshotPath, fullPage: true });
    }

    assert(failures.length === 0, failures.join("\n"));
    console.log(JSON.stringify({
      ok: true,
      document: expectedDocument,
      citationText: citations,
      evidenceCount: trace.evidence.length,
      versionExercised: true,
      pagePreviewExercised: true,
      accessExercised: true,
      folderExercised: true,
      virtualNodeExercised: true,
      invitationExercised: true,
      conversationExportExercised: true,
      tokenExercised: true,
      tokenPolicyExercised: true,
      auditExercised: true,
      workspaceExportExercised: true,
      workspaceImportPreviewExercised: true,
      retentionExercised: true,
      readinessExercised: true,
      providerExercised: true,
      screenshotPath: screenshotPath || null
    }));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
