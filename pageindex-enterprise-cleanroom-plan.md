# PageIndex Enterprise Clean-Room Reimplementation Plan

Date: 2026-06-23
Workspace: /Users/alaxise/repo/PageIndex

## Scope

This report studies the public PageIndex surfaces only:

- Public repository: https://github.com/VectifyAI/PageIndex
- Public docs: https://docs.pageindex.ai/
- Public product pages: https://pageindex.ai/
- Public chat landing/demo: https://chat.pageindex.ai/
- Public GitHub issues and pull requests

Clean-room boundary: do not bypass authentication, scrape private dashboard data, replay private API traffic, or copy closed-source backend behavior. The plan below reimplements visible behavior and documented concepts from public sources.

## Executive Conclusion

The missing enterprise feature is not just "allow `doc_id` to be a list." Public PageIndex OSS is a strong single-document tree retrieval system. The enterprise-only layer appears to be a corpus-level file system/search layer that turns many document trees into one queryable workspace:

- single index over millions of documents
- PageIndex File System for corpus-level routing
- virtual nodes above document trees
- query-dependent index construction
- dynamic flattening of weak folder structures
- hybrid value-based plus LLM tree search
- enterprise deployment/security/RBAC/audit controls

The clean-room plan should therefore build a corpus retrieval layer on top of the existing per-document tree index, then harden it into an enterprise workspace system.

## Implementation Status On 2026-06-28

The current branch implements a release-ready local enterprise MVP for the backend, CLI, HTTP API, and local dashboard surfaces. It does not claim to copy private PageIndex cloud internals; it reimplements the public enterprise behaviors through independently designed storage, retrieval, authorization, audit, packaging, and verification code.

Implemented and verified surfaces:

- Multi-workspace tenant model with members, roles, invitations, API tokens, token policy, role-aware scopes, expiration, rotation, and strict Bearer-token HTTP mode.
- Workspace folders with nested paths, move/rename/delete lifecycle, folder-scoped ingest/query/chat, inherited folder grants, effective access previews, deny precedence, and bulk ACL import/revoke controls.
- Multi-document retrieval with source sets, folder scopes, query history, trace evidence, citations, line-level citation validation, virtual nodes, query-dependent tree planning, and deterministic hybrid evidence selection.
- Conversation and Chat Completions surfaces, including scoped conversations, folder/source-set scope updates, generated titles, archive/rename/delete, transcript export, public share links, and streaming Chat Completions metadata.
- Document lifecycle controls for upload, import, reindex, delete, versions, page previews, suggested questions, share links, and workspace export/import preservation of managed uploads.
- Enterprise operator controls for provider configuration, deployment readiness, eval harness, audit ledger/integrity/export, audit/query retention, legal hold, workspace usage, SIEM-style JSONL audit sinks, and sink delivery readiness.
- Release hardening for wheel packaging, console entrypoint, release manifest, SBOM, dependency/build/artifact/secret gates, GitHub Actions release smoke, and summary rendering.

Fresh acceptance evidence collected on 2026-06-28:

- Full enterprise unit suite: `python -m unittest discover -s tests -p 'test*.py' -v` ran 204 tests in 303.916s with `OK (skipped=1)`, zero FAIL markers, and zero ERROR markers.
- Dashboard browser smoke: `tests.test_enterprise_store.EnterpriseStoreTest.test_dashboard_playwright_smoke_interacts_with_local_app_when_available` ran with bundled Node/Playwright in 8.730s with `OK` and no skip markers.
- Clean-source release smoke: `scripts/release_smoke.py --require-clean-source` returned `release_ok=True`, `source_clean=True`, `source_dirty=False`, eval checks `17/17`, deployment checks `9/9`, and passing secret, build, dependency, artifact, and SBOM gates.
- Remote evidence: `origin/codex/enterprise-cleanroom` points to `6d064030500a3d854867000ce1e9f3c10a84b1c6`; GitHub Actions run `28319968633` completed successfully for that SHA.

Completion call:

- Backend/API/CLI/local-dashboard enterprise clean-room MVP: complete for release-readiness purposes.
- Full hosted cloud product parity: not claimed until a separate product decision accepts or rejects SaaS-only surfaces such as billing checkout, account identity provider integration, private deployment automation, live hosted storage, and exact visual parity with the authenticated PageIndex cloud dashboard.

## Evidence Inventory

### Official Product And Docs Evidence

- PageIndex File System announcement: https://pageindex.ai/blog/pageindex-filesystem
  - Enterprise GA includes single-index scale to millions of documents, virtual-node synthesis, query-dependent index construction, and dedicated/VPC deployment.
  - It describes a file-level tree above document-level PageIndex trees.
  - It describes virtual nodes, query-conditioned tree construction, and dynamic flattening.
- Enterprise page: https://pageindex.ai/enterprise
  - Lists enterprise security, flexible cloud/on-prem/hybrid/VPC deployment, dedicated support, custom integrations, data privacy/no training, analytics, audit logs, reporting.
- Subscription docs: https://docs.pageindex.ai/subscription
  - Standard: MCP/API, 10k active pages, citations, vision.
  - Pro: lab features, 50k pages.
  - Max: 500k pages, multiple workspaces, priority support.
  - Enterprise: private deployment, advanced security/compliance, custom integrations/API, SLAs, dedicated support.
- Chat product page: https://pageindex.ai/chat
  - Publicly advertises cross-document analysis, Team plan advanced file search, granular file access controls, multiple users, private deployment, and access to most accurate model.
- Chat API docs: https://docs.pageindex.ai/sdk/chat and https://docs.pageindex.ai/api-reference
  - `doc_id` can be a string or list.
  - Streaming exists.
  - Citations can be enabled.
  - Streaming metadata exposes tool-use style blocks.
- Folder/workspace docs: https://docs.pageindex.ai/sdk/folders
  - Max-plan folders/workspaces organize documents, support nested folders, document upload into folders, list by folder, pagination.
- Document search docs: https://docs.pageindex.ai/tutorials/doc-search
  - State that PageIndex is single-document by default.
  - Recommend metadata, semantics, or descriptions for multi-document search.
- Metadata search docs: https://docs.pageindex.ai/tutorials/doc-search/metadata
  - Metadata support is closed beta.
  - Recommended pattern: upload documents, store metadata plus `doc_id`, query-to-SQL selects relevant documents, then use PageIndex retrieval.
- Hybrid tree search docs: https://docs.pageindex.ai/tutorials/tree-search/hybrid
  - Value search chunks node content, retrieves top chunks, maps chunk scores back to nodes, and returns nodes rather than chunks.
  - Hybrid search runs value-based and LLM-based tree search in parallel, merges unique nodes, consumes nodes, and terminates early when enough evidence is gathered.

### Public OSS Baseline

Observed in the public repository cloned to `/tmp/pageindex-study` at commit `293730afbd4319a683fe4aee439360a2b21b8c3c`:

- `PageIndexClient.index()` creates one `doc_id` per file.
- Workspace persistence stores multiple document trees, but retrieval functions are per-document.
- `get_document`, `get_document_structure`, and `get_page_content` accept a single `doc_id` on main.
- The demo agent binds tools around one selected `doc_id`.
- Tutorial docs say PageIndex enables reasoning-based RAG within a single document by default.

### Public Chat/UI Crawl

Headless Playwright crawl artifacts:

- Summary: `/tmp/pageindex-crawl/out-fast/summary.json`
- Screenshots: `/tmp/pageindex-crawl/out-fast/screenshots/`
- Focused UI probe: `/tmp/pageindex-crawl/out-fast/ui-probe.json`
- Cloud chatbot interaction screenshot: `/tmp/pageindex-crawl/out-fast/cloud-chat-interaction.png`

Observed public unauthenticated UI:

- `chat.pageindex.ai/` shows public sample documents and a question box.
- Sample categories include textbooks, financial reports, legal documents, research papers, and business plans.
- Public sample docs include PRML, Federal Reserve annual report, Dodd-Frank Act, a context-engineering survey, and a UK Power Networks business plan.
- It exposes "Add your own documents" and a file input, but authenticated use is required.
- Login supports Google, GitHub, email, and password.
- `dash.pageindex.ai/*` routes redirect to login, so API keys, subscription, and dashboard management were not inspected beyond login.

Additional cloud chatbot pass on 2026-06-23:

- Submitting a question against the public PRML sample document redirects to login instead of returning an answer unauthenticated.
- The redirect preserves a callback payload containing the selected `doc_id` and the prompt, which confirms the cloud chat product routes questions through an authenticated execution path.
- The bundled public client exposes plan and teamspace strings: Enterprise includes "Access to our most accurate model", "Advanced File Search", "Granular file access controls", "Support for multiple users", "Private deployment option", and "Dedicated support".
- The same public client exposes Team Space and Personal Space concepts, including "A shared workspace for your team with one plan and one bill" and switching between private documents and shared team-space documents.
- The public client includes client-side permission concepts for `Document`, `Folder`, `Chat`, `Teamspace`, `TeamspaceMember`, `TeamspaceInvitation`, and `Billing`, with Owner/Admin role distinctions.
- The public client includes citation parsing helpers for document/page/block citations.

Interpretation: the cloud chatbot does not overturn the architecture conclusion. It does strengthen the product-surface priority: a credible enterprise clone should include teamspaces, personal vs shared workspaces, billing/usage/top-up surfaces, document/folder permissions, share links, and citation rendering earlier than the first report implied.

### Public Issues And PRs

- Issue #187: appending multiple document trees only traverses the first tree for cross-document questions.
- Issue #284: asks whether PageIndex can build a unified tree over dozens of PDFs or must treat each file separately.
- Issue #300: `list_documents()` is unusable for 10,000+ docs because the LLM sees full metadata; requester proposes `search_documents(query)` or a global workspace TOC.
- Issue #316: requests incremental updates via changed-section detection, subtree rebuilds, summary recomputation along impacted paths, and version history.
- PR #216: open PR adding multi-document retrieval/client support by accepting `str | list[str]` doc IDs.
- PR #299: open PR for scoped query mode and collection improvements, including multi-doc support and prompt-injection guarded document context.
- PR #302: open PR adding PageIndex FileSystem/PIFS CLI with virtual folders, registered files, metadata, PageIndex/projection status, path resolution, SQLite persistence, and bounded/auditable reads.
- PR #139: open PR adding batch processing and small/medium knowledge-base search.

Interpretation: public contributors independently identified the same gap. Existing PRs cover useful slices, but none constitute the full enterprise corpus layer described by PageIndex's product/docs.

## Missing Feature Map

| Area | Public OSS | Cloud/API/Plan Evidence | Enterprise-Like Target |
| --- | --- | --- | --- |
| Per-document indexing | Yes | Cloud API uploads PDFs and builds tree/OCR | Keep as document tree substrate |
| Multi-doc scoped chat | No first-class mainline support | Chat API accepts `doc_id` string or array | Add corpus query API with doc scopes |
| Document discovery | Weak `list_documents` only | Folders and metadata workflows | Add `search_documents`, filters, ranking |
| Metadata search | Manual tutorial, closed beta | Query-to-SQL recommendation | Add metadata extractor + SQL/FTS router |
| Workspace/folders | Local workspace persistence only | Max plan folders/workspaces | Add nested folders, path scopes, pagination |
| Cross-document reasoning | Not reliable by default | Chat page advertises cross-doc analysis | Candidate docs -> per-doc evidence -> synthesis |
| PageIndex File System | Not in main | Enterprise File System blog, open PIFS PR | Build virtual corpus DAG above doc trees |
| Query-dependent corpus tree | Not in main | Enterprise docs/blog | Build per-query virtual tree planner |
| Dynamic flattening | Not in main | Enterprise docs/blog | Flatten weak/ambiguous nodes at query time |
| Hybrid fast tree search | Tutorial only | Retrieval API uses it by default | Implement value + LLM parallel search |
| Citations/traces | Demo-level | API citations and stream metadata | Evidence ledger, node/page citations, traces |
| Vision/OCR quality | Standard parser in OSS | Paid plans include vision understanding; cloud OCR | Pluggable OCR/vision pipeline |
| Enterprise security | No | Enterprise page and subscription docs | Auth, RBAC, audit logs, private deploy |
| Teamspaces and roles | No | Cloud chatbot bundle exposes teamspace, Owner/Admin roles, invitations, billing | Add personal/team spaces, roles, invitations |
| Advanced file search | No | Enterprise plan string in cloud chatbot bundle | Add workspace search over documents/folders/nodes |
| Incremental updates | No | Issue #316 demand | Hash/versioned node update subsystem |

## Clean-Room Architecture

### Core Abstractions

Implement a new corpus layer without altering the per-document tree generator first.

```python
class DocumentStore:
    def submit_document(path, metadata=None, folder_id=None) -> str: ...
    def get_document(doc_id) -> DocumentMeta: ...
    def get_tree(doc_id, include_summaries=False) -> Tree: ...
    def get_page_content(doc_id, pages) -> PageContent: ...

class CorpusStore:
    def list_documents(folder_id=None, limit=50, offset=0) -> Page[DocumentMeta]: ...
    def search_documents(query, filters=None, folder_id=None, top_k=20) -> list[DocumentHit]: ...
    def query(query, doc_ids=None, folder_id=None, filters=None, stream=False) -> Answer: ...

class VirtualFileSystem:
    def build_workspace_index(workspace_id) -> None: ...
    def plan_query_tree(query, scope) -> VirtualTree: ...
    def browse(path, query=None, filters=None) -> list[VirtualNodeHit]: ...
    def read(path_or_doc_id, node_id=None, pages=None) -> Evidence: ...
```

### Storage Model

Start with SQLite because it gives transactions, pagination, JSON columns, and FTS5 without adding a service dependency.

- `documents(id, name, description, page_count, status, folder_id, created_at, updated_at, source_hash, tree_path, ocr_path)`
- `document_metadata(doc_id, key, value, value_type, confidence, provenance)`
- `document_nodes(doc_id, node_id, parent_node_id, title, summary, page_start, page_end, text_ref)`
- `node_chunks(doc_id, node_id, chunk_id, text, embedding_ref, bm25_terms)`
- `folders(id, parent_id, name, description, path, created_at, updated_at)`
- `virtual_nodes(id, workspace_id, kind, label, summary, axis, query_signature, created_at)`
- `virtual_edges(parent_id, child_id, edge_type, weight, reason)`
- `virtual_node_docs(virtual_node_id, doc_id, weight, reason)`
- `query_runs(id, query, scope_json, plan_json, started_at, completed_at, cost_json)`
- `evidence(run_id, doc_id, node_id, page_start, page_end, quote_hash, citation_label, score)`
- `audit_log(id, actor_id, action, object_type, object_id, metadata_json, created_at)`
- `document_versions(doc_id, version, source_hash, parent_version, changed_nodes_json, created_at)`

### Phase 1: Multi-Document Query MVP

Goal: close the obvious OSS gap while preserving behavior.

Features:

- Accept `doc_ids: str | list[str] | None`.
- If `doc_ids` is a string, preserve single-doc behavior.
- If `doc_ids` is a list, retrieve metadata/structures/page content per document and return a doc-keyed result.
- Add `search_documents(query)` over document names, descriptions, metadata, and root summaries.
- Add `query_corpus(query, doc_ids=None, folder_id=None, filters=None)`.

Algorithm:

1. Route query to candidate docs using SQLite FTS over titles, descriptions, root summaries, metadata, and optional tags.
2. For each candidate doc, run the existing single-document tree retrieval.
3. Normalize evidence into `(doc_id, doc_name, node_id, pages, text, score)`.
4. Synthesize with an answer prompt that requires citations and permits "not found."
5. Return answer, citations, per-doc evidence, and retrieval trace.

Acceptance tests:

- Single-doc output is backward compatible.
- Multi-doc query inspects at least two relevant docs when evidence spans both.
- No full workspace metadata dump enters the LLM context.
- Prompt injection in document metadata/content cannot redefine tool instructions.

### Phase 2: Metadata, Description, And Semantic Routing

Goal: implement the public doc-search workflows as first-class code.

Features:

- Metadata extraction during ingestion: document type, dates, entities, organizations, jurisdictions, fiscal periods, product names, topics, and short description.
- Query planner that converts user intent into SQL/FTS filters plus residual semantic query.
- Description index for small collections.
- Optional vector index for document descriptions and node summaries, used only as a value prior and not as final evidence.

Routing flow:

1. Classify query intent: lookup, compare, aggregate, temporal, entity-specific, global exploratory.
2. Generate filter candidates: folder path, document type, date range, entity, topic.
3. Execute SQL/FTS and optional semantic search.
4. Return a small candidate set with transparent reasons.

### Phase 3: PageIndex File System Clean-Room Clone

Goal: reproduce the public behavior of enterprise corpus navigation without copying private implementation.

Concept:

- Physical folders remain stable user-owned paths.
- Virtual folders are generated views: by topic, entity, year, status, geography, product, document type, case, account, or query-specific axis.
- A document can appear under multiple virtual ancestors.
- Query-dependent tree construction creates a temporary tree optimized for the current query.

Implementation:

1. Build `workspace_root` with physical folder children and virtual namespace children, for example:
   - `/physical/...`
   - `/virtual/by-topic/...`
   - `/virtual/by-entity/...`
   - `/virtual/by-year/...`
   - `/query/<run_id>/...`
2. Generate virtual nodes with clustering over metadata, descriptions, root summaries, and entity sets.
3. For a query, choose axes with an LLM or deterministic planner:
   - "compare FY2023 Fed and bank reports" -> year, organization, report type
   - "contracts with indemnification" -> clause/topic, counterparty, effective date
4. Build a bounded query tree with summaries and counts.
5. Dynamically flatten nodes whose labels are ambiguous or whose children are too numerous/low-signal.
6. Expose shell-like agent tools: `ls`, `find`, `grep`, `cat`, `tree`, `metadata`, `retrieve`.

Acceptance tests:

- A 10,000-document synthetic workspace can route without dumping metadata.
- Query tree includes only useful hierarchy for the query.
- Documents can appear in multiple virtual folders.
- Dynamic flattening reduces traversal depth when labels are unhelpful.

### Phase 4: Fast Hybrid Tree Search

Goal: implement the documented hybrid search behavior.

Components:

- LLM tree search: reads node titles/summaries and selects promising branches.
- Value tree search: chunks node content, scores chunks with BM25/embedding/reranker, aggregates chunk scores to parent nodes with a diminishing-return normalization.
- Merge queue: deduplicates nodes from both searches.
- Node consumer: reads/summarizes evidence from queued nodes.
- Early-stop agent: stops when enough evidence exists or budget is exhausted.

Pseudo-flow:

```python
async def hybrid_tree_search(query, virtual_tree, budget):
    queue = UniquePriorityQueue()
    llm_task = run_llm_tree_search(query, virtual_tree, queue, budget.llm)
    value_task = run_value_tree_search(query, virtual_tree, queue, budget.value)

    evidence = []
    while not budget.exhausted():
        node = await queue.get_next()
        item = consume_node(query, node)
        evidence.append(item)
        if enough_evidence(query, evidence):
            break

    await cancel_remaining(llm_task, value_task)
    return rank_evidence(evidence)
```

Acceptance tests:

- Value-only, LLM-only, and hybrid modes are individually testable.
- Hybrid finds evidence missed by either branch alone on seeded fixtures.
- Early stop preserves citation completeness.
- Search emits a trace of selected/rejected nodes.

### Phase 5: Cross-Document Reasoning

Goal: support questions whose answer spans documents.

Reasoning modes:

- Compare: align evidence by entity/date/metric/topic.
- Aggregate: compute simple counts/sums/tallies from extracted evidence.
- Multi-hop: find bridge entities across documents, then retrieve connected evidence.
- Conflict check: detect disagreement between documents and cite both sides.
- Literature/survey synthesis: cluster papers by contribution, method, dataset, result, limitation.

Evidence contract:

- Every claim must bind to one or more evidence records.
- Each evidence record must include doc ID/name, node ID, page range, content hash, and extraction reason.
- Generated answer carries inline citations, plus a machine-readable citation table.

### Phase 6: Enterprise Controls

Goal: match enterprise expectations around deployment and governance.

Features:

- Personal spaces, teamspaces, folders, and nested scopes.
- Users, groups, invitations, Owner/Admin/member roles, and document/folder ACLs.
- API keys with scopes and rate limits.
- Audit logs for ingestion, deletion, query, export, admin actions.
- Encryption at rest and TLS in transit.
- Tenant isolation and private deployment config.
- Data retention and deletion jobs.
- Usage analytics and cost reports.
- Admin dashboard for documents, folders, users, teamspaces, API keys, billing/quotas, and audit search.
- Share links for chat and document views with permission checks.

### Phase 7: Incremental Indexing

Goal: handle enterprise document updates efficiently.

Implementation:

- Hash source pages and normalized content blocks.
- Map changed blocks to document tree nodes.
- Rebuild only affected subtrees.
- Recompute ancestor summaries up to root.
- Preserve version history and support diff views.
- Mark stale virtual nodes and update affected corpus indexes.

Acceptance tests:

- Two-page update in a 500-page fixture does not rebuild unrelated nodes.
- Version comparison shows changed nodes and changed citations.
- Query results do not cite stale deleted content after an update.

## API Sketch

```http
POST /documents
GET /documents?folder_id=&limit=&offset=
GET /documents/search?q=&folder_id=&filters=
GET /documents/{doc_id}
GET /documents/{doc_id}/tree
GET /documents/{doc_id}/pages?range=1-3
DELETE /documents/{doc_id}

POST /folders
GET /folders?parent_folder_id=

POST /chat/completions
{
  "messages": [{"role": "user", "content": "..."}],
  "doc_id": "pi-123" | ["pi-123", "pi-456"] | null,
  "folder_id": "folder-123",
  "filters": {"company": "Acme", "year": 2025},
  "stream": true,
  "stream_metadata": true,
  "enable_citations": true
}

POST /retrieval/search
{
  "query": "...",
  "scope": {"doc_ids": [], "folder_id": null, "filters": {}},
  "mode": "llm" | "value" | "hybrid",
  "return_trace": true
}
```

## Implementation Order

1. Add SQLite corpus manifest and `search_documents`.
2. Add multi-doc `doc_id` support and doc-scoped query orchestrator.
3. Add citations and evidence ledger.
4. Add folder/workspace API with pagination.
5. Add metadata extraction and query-to-SQL routing.
6. Add hybrid tree search over one document.
7. Generalize hybrid tree search to corpus virtual trees.
8. Add virtual folders and query-dependent PIFS.
9. Add enterprise auth/RBAC/audit/tenant boundaries.
10. Add incremental indexing and versioning.

## Verification Plan

Datasets:

- 20 annual reports with recurring metrics and dates.
- 20 legal/regulatory PDFs with repeated clause names.
- 20 academic papers for survey synthesis.
- 1,000 to 10,000 synthetic document manifests for routing stress tests.
- Versioned policy manual with small updates.

Metrics:

- Candidate document recall at k.
- Evidence node recall.
- Citation precision.
- Unsupported-claim rate.
- Cross-document answer correctness.
- Latency and token cost.
- LLM context size per query.
- Audit trace completeness.

Required tests:

- Unit tests for stores, filters, routing, citations, ACL decisions.
- Golden tests for query plans and answer citations.
- Property tests for folder/path resolution.
- Regression tests for prompt injection in metadata/content.
- Load tests for `search_documents` and virtual tree construction.

## Known Unknowns And Risks

- The exact enterprise backend is not public. The plan infers architecture from product/docs, not private code.
- PageIndex cloud OCR/vision quality may depend on proprietary models. Reimplementation should use pluggable OCR/vision providers.
- Public dashboard surfaces are auth-gated; only login and unauthenticated public app shell were crawled.
- Hybrid tree search details beyond the published docs are unspecified; the implementation should be measured against behavior, not assumed internals.
- Multi-document synthesis can easily hallucinate if evidence discipline is weak. Treat citation coverage as a release blocker.

## Recommended MVP Cut

Build the smallest credible enterprise missing-feature clone:

1. SQLite workspace manifest with folders, metadata, and FTS.
2. `search_documents(query)` that never dumps all docs to the LLM.
3. `query_corpus(query, doc_ids=None, folder_id=None, filters=None)` that routes to candidate docs, runs existing per-doc PageIndex retrieval, and synthesizes with citations.
4. Streaming trace events for document selection, node selection, and citation assembly.
5. Evaluation harness with cross-document comparison, aggregation, and "not found" cases.

That MVP directly addresses the most visible public gaps: cross-document querying, large workspace discovery, metadata routing, and auditable citations. The PageIndex File System and enterprise hardening can then land incrementally on top of that stable corpus core.
