# 🧭 Freshservice Semantic Search — End-to-End Audit Plan

**Status:** Proposed (not yet executed)
**Prepared:** 2026-06-15
**Scope:** Entire repository — application code, AI layer, data/ingestion, configuration, tests, documentation, security, and repo hygiene.
**Goal:** A complete, evidence-based audit that makes the project **correct, efficient, lean, and well-documented**, removing anything unused and bringing all docs in line with reality.

> This document is the *plan*. Nothing here has been changed yet. Each work item below has an ID (e.g. `C1`, `D3`) so we can track execution. A condensed "head-start findings" appendix at the end lists concrete issues already discovered during the planning sweep so execution can begin immediately.

---

## 1. Project at a Glance (as-found)

A local **Streamlit** app (`app.py`, ~1,515 lines) plus a set of Python modules that provide semantic search over historical Freshservice tickets, backed by a **ChromaDB** vector store and **OpenAI** embeddings/LLM features.

| Area | Files | Notes |
|------|-------|-------|
| Web UI | `app.py` | Streamlit UI, unassigned-ticket dashboard, AI guidance panel, ticket updates |
| Config | `config.py` | Env loading, FS/OpenAI/Chroma clients |
| Ingestion | `freshservice.py` | Pulls closed incidents → embeds into Chroma |
| Search core | `search_tickets.py`, `search_intent.py`, `search_context.py` | Retrieval, reranking, intent tokens, context fetch |
| AI layer | `ai_recommendations.py`, `ai_summarizer.py`, `improved_ai_prompt.py` | Guidance + summarization + prompt builders |
| Utilities | `agent_resolver.py`, `text_cleaning.py`, `debug_utils.py` | Name resolution, HTML cleanup, diagnostics |
| Startup | `start_app.py` | Pre-flight checks + launch |
| Maintenance | `maintenance/categories.py` | Exports category taxonomy → `categories.json` |
| Tests | `tests/` (3 files) | 2 real unit tests + 1 API-hitting script |
| Docs | 9 markdown files (~2,800 lines) | Significant overlap + drift |

**Stack actually installed (`.venv`, Python 3.12.6):** `openai==0.28.1`, `chromadb==0.4.22`, `streamlit==1.37.0`, `requests==2.32.3`, `python-dotenv==1.0.1`, `beautifulsoup4==4.12.3`, `numpy==1.26.4`, `pandas==2.3.2`. **`pytest` is not installed.**

**Vector store:** on-disk Chroma collection is named **`FreshService`** and contains **4,484** documents.

---

## 2. Audit Objectives

1. **Correctness** — find latent/real bugs and runtime fragilities (esp. dependency drift, deprecated APIs, missing data files).
2. **Reproducibility** — anyone can clone, install, and run the project from a clean machine.
3. **Efficiency** — reduce redundant API calls, session/client churn, and wasted work.
4. **Leanness** — delete dead code, unused imports, transient debug docs, and local clutter.
5. **Documentation truth** — every doc statement matches the code and data as they actually are.
6. **Security** — no secret leakage, no injection vectors, safe defaults.
7. **Maintainability** — a real test suite, pinned deps, and a single source of truth for config.

---

## 3. Methodology & Phases

The audit runs in **8 phases**. Each phase is independently shippable. Phases 0–3 are the "must-fix" backbone (a fresh clone won't run today); 4–7 are quality, leanness, and durability.

```
Phase 0  Baseline & safety net        (snapshot, branch, inventory)
Phase 1  Dependency & runtime audit    (the project won't install cleanly today)
Phase 2  Configuration & data audit    (collection name, missing JSON, env truth)
Phase 3  Correctness & bug audit        (deprecated APIs, edge cases, error paths)
Phase 4  Code quality & dead-code purge (unused imports, duplication, structure)
Phase 5  Efficiency & architecture      (sessions, N+1 calls, caching)
Phase 6  Security & secrets audit       (api.env, XSS via HTML, history scan)
Phase 7  Testing, CI & documentation    (real tests, doc consolidation/rewrite)
```

Each work item is tagged **[P#]** with a severity:
🔴 Critical (breaks/blocks) · 🟠 High · 🟡 Medium · 🟢 Low/polish.

---

## Phase 0 — Baseline & Safety Net

**Objective:** Make the audit reversible and measurable before touching anything.

| ID | Task | Severity |
|----|------|----------|
| B1 | Create a working branch (e.g. `audit/cleanup`) off `main`; do not commit to `main` directly. | 🟠 |
| B2 | Capture a frozen snapshot of the **working** environment: `pip freeze > requirements.lock.txt` (reference for the real, working versions). | 🔴 |
| B3 | Back up the Chroma DB (`chroma_db/`) and `api.env` outside the repo before any data/config change. | 🔴 |
| B4 | Record a behavioral baseline: launch the app, run 2–3 known searches + one AI-guidance call, screenshot/log results to compare against post-change behavior. | 🟠 |
| B5 | Generate an automated inventory: per-file line counts, import graph, and a "referenced-but-missing files" list (seed list in Appendix A). | 🟡 |

**Deliverables:** branch, `requirements.lock.txt`, backups, baseline notes.
**Acceptance:** we can restore the exact working state at any point.

---

## Phase 1 — Dependency & Runtime Audit  🔴 (highest priority)

**Why first:** A clean `git clone` **cannot run** today — `requirements.txt` is referenced everywhere (README, `start_app.py`, `TROUBLESHOOTING.md`) **but does not exist**. A naive `pip install openai chromadb …` pulls `openai>=1.0`, which **removes** the `openai.ChatCompletion`/`openai.Embedding` APIs this code uses — silently breaking AI guidance, summarization, and diagnostics.

| ID | Task | Severity |
|----|------|----------|
| D1 | Author a **pinned `requirements.txt`** (and/or `pyproject.toml`) reflecting the known-good versions from B2. | 🔴 |
| D2 | Decide the OpenAI strategy (see decision box). Either **(a) pin `openai<1.0`** to keep current code working, or **(b) migrate** all call sites to the `openai>=1.x` client. | 🔴 |
| D3 | If migrating (D2b): update `ai_recommendations.py`, `ai_summarizer.py`, `debug_utils.py` to `OpenAI()` client + `client.chat.completions.create` + `.choices[0].message.content`. **Verify Chroma's `OpenAIEmbeddingFunction` (chromadb 0.4.22) stays compatible** — its embedding call also assumes a specific openai major version, so embeddings + ingestion must be retested. | 🔴 |
| D4 | Split runtime vs. dev dependencies (`pytest`, lin/format tooling) into `requirements-dev.txt` or `pyproject` extras. | 🟡 |
| D5 | Validate a **from-scratch install** in a throwaway venv: install → diagnostics → search → guidance → ingest dry-run. | 🔴 |
| D6 | Re-evaluate the ChromaDB version story: code comments + error messages reference both `0.4.22` and "Chroma 0.5.x"/`get_or_create_collection`. Pick a target, update the `config.py` fallback logic and messages to match. | 🟠 |

> **DECISION NEEDED — OpenAI SDK:** keep legacy (`openai==0.28.1`, lower effort, frozen-in-time) vs. migrate to `openai>=1.x` (future-proof, but must re-verify Chroma's embedding function and ingestion). Recommendation: **migrate**, but only with full ingestion/search re-test, because the embedding path is shared with Chroma.

**Deliverables:** `requirements.txt`, `requirements-dev.txt`, updated install docs, clean-install validation log.
**Acceptance:** fresh clone → `pip install -r requirements.txt` → app runs, AI features work, ingestion works.

---

## Phase 2 — Configuration & Data Integrity Audit  🔴/🟠

**Why:** The app currently only works because `api.env` overrides defaults. Several defaults are wrong, and two data files the code reads are missing.

| ID | Task | Severity |
|----|------|----------|
| G1 | **Collection-name mismatch:** `config.py` default = `freshservice_core`, but the real collection (and `debug_utils.py` default) = `FreshService`. A default-only run would target an empty collection. Unify to one canonical name and update all references. | 🔴 |
| G2 | **Missing `categories.json`:** `load_category_tree()` and `_load_known_tokens()` both read it; it's absent, so AI guidance gets an **empty taxonomy** and token detection falls back to 11 hardcoded terms. Run `python -m maintenance.categories` to (re)generate it; decide whether to commit it or document generation as a required setup step. | 🔴 |
| G3 | **Missing `raw_ticket_fields.json`:** `app.py` `_status_choices()` reads it and silently falls back to hardcoded statuses. Generate (it's a side-output of `maintenance/categories.py`) or remove the dead load path. | 🟡 |
| G4 | Provide **`api.env.example`** (referenced by README `cp api.env.example api.env` but missing) with all keys documented and **no secrets**. | 🟠 |
| G5 | Audit **every env var** in `config.py`/`freshservice.py`/`app.py` for: documented in README? present in `api.env.example`? sane default? Build one canonical config reference table; delete undocumented/unused knobs. | 🟠 |
| G6 | **Data validation:** the collection holds 4,484 docs but README claims 3,660. Verify what's actually indexed (status/type filters, `doc_type=="core"`), check for stale/duplicate/orphaned docs, and confirm the count, ticket-ID range, and top categories so docs can be corrected with real numbers. | 🟠 |
| G7 | Define the **data refresh runbook**: how/when to run `freshservice.py` (incremental `--since-days`), how to refresh `categories.json`, and how to back up Chroma. | 🟡 |

**Deliverables:** unified config defaults, generated/committed (or documented) data files, `api.env.example`, a verified config reference, data-integrity report.
**Acceptance:** running with **defaults only** (no `api.env` overrides except secrets) targets the correct collection and loads a real taxonomy.

---

## Phase 3 — Correctness & Bug Audit  🟠

**Objective:** Find and fix real and latent bugs, focusing on error paths and edge cases.

| ID | Task | Severity |
|----|------|----------|
| C1 | **Deprecated Streamlit API:** `app.py:1141,1145` call `st.experimental_rerun()` (removed in current Streamlit; rest of the file uses `st.rerun()`). Reachable from the empty-results "Allow other…" buttons. Replace + audit all rerun/session-state flows. | 🟠 |
| C2 | Audit the **`retrieve_similar_tickets` where-chain** (`incident` → `Incident` → `None`): confirm metadata actually stores `type` and whether the 3-attempt fallback is still meaningful or vestigial. | 🟡 |
| C3 | Audit **error handling consistency**: `app.py` mixes broad `except Exception` with `st.error`; some branches swallow `RerunException` specially. Verify reruns never get caught; standardize the pattern. | 🟡 |
| C4 | **Agent resolution N+1:** `_resolve_assigned_agent` issues an extra `/tickets/{id}` GET when `responder_name` is missing, then `/agents/{id}` — per result. On large result sets this is slow and rate-limit-prone. Validate correctness and measure. | 🟠 |
| C5 | **Ticket update verification path** (`_update_ticket_fields`): confirm the "accepted but unchanged" mismatch detection works against the real FS API (category/sub_category/item_category/group_id field names vary). | 🟠 |
| C6 | **Category inference** (`_infer_category_item`) + `_category_payload_from_path`: verify taxonomy key casing matches real `categories.json`; today taxonomy is empty so this path is untested in practice. | 🟡 |
| C7 | Review **timezone/date parsing** (`created_at` handling in dashboard) and `_safe_int`/`_safe_trim` edge cases. | 🟢 |
| C8 | Confirm **graceful AI fallback** actually triggers (summarizer/guidance) when the OpenAI call fails — tie to the Phase 1 SDK decision. | 🟠 |

**Deliverables:** bug list with repro + fixes, regression notes against the Phase 0 baseline.
**Acceptance:** no deprecated API calls remain; all known edge cases handled or documented.

---

## Phase 4 — Code Quality & Dead-Code Purge  🟡

**Objective:** Remove everything unused; reduce duplication; improve readability without behavior change.

| ID | Task | Severity |
|----|------|----------|
| Q1 | **Remove dead imports** in `app.py`: `AIGuidance`, `SystemDiagnostics`, `handle_streamlit_error`, `safe_import` are each imported but never used. | 🟡 |
| Q2 | **Dead/unused functions:** `handle_streamlit_error` (decorator) and `safe_import` (helper) in `debug_utils.py` appear unused anywhere → delete or wire in. | 🟡 |
| Q3 | **Decompose `app.py`** (~1,515 lines): extract dashboard, card rendering, guidance panel, and ticket-update logic into modules (e.g. `ui/`). Improves testability + readability. | 🟠 |
| Q4 | **De-duplicate text helpers:** `search_context._clean_text` re-wraps `text_cleaning.html_to_text`; consolidate `_safe_int`/`_safe_trim` (duplicated across `app.py` and `search_context.py`) into one shared util. | 🟡 |
| Q5 | Resolve the **`_extract_preview_text` TODO** (it admits it should show AI summaries, not raw text) — implement or remove the TODO + decide intended UX. | 🟢 |
| Q6 | **Branding:** app title is `🔎 Nexus` (`app.py:131`) while every doc says "Freshservice Semantic Search." Pick one name and apply consistently. | 🟡 |
| Q7 | **Logging hygiene:** multiple modules call `logging.basicConfig(...)` at import time (`app.py`, `search_tickets.py`, `freshservice.py`, `debug_utils.py`) — competing root configs. Centralize logging setup. | 🟡 |
| Q8 | Introduce **lin/format tooling** (`ruff` + `black`/`ruff format`) and apply; add config. Resolves trailing-whitespace/inconsistent-blank-line noise flagged in past commits. | 🟢 |
| Q9 | Add **type-checking pass** (`mypy`/`pyright`) on the now-smaller modules; fix the easy wins. | 🟢 |

**Deliverables:** smaller `app.py`, shared utils module, lint/format config, dead-code removal diff.
**Acceptance:** `ruff` clean; no unused imports/functions; behavior unchanged vs. baseline.

---

## Phase 5 — Efficiency & Architecture Audit  🟡

**Objective:** Cut redundant work and clarify the architecture.

| ID | Task | Severity |
|----|------|----------|
| E1 | **Session reuse:** `freshservice_session()` builds a brand-new `requests.Session` on nearly every call in `agent_resolver.py`, `search_tickets.py`, `search_context.py` (Streamlit caches one, CLI does not). Introduce a shared/pooled session; the README already *claims* session reuse. | 🟠 |
| E2 | **Chroma client/embedding reuse:** `chroma_collection()` rebuilds a `PersistentClient` + `OpenAIEmbeddingFunction` every call. Cache the client (and in Streamlit via `@st.cache_resource`). | 🟡 |
| E3 | **Ingestion dedupe:** `_exists()` does one `coll.get()` per ticket → O(N) round-trips on reingest. Pre-fetch existing IDs once and diff. | 🟡 |
| E4 | **Retrieval sizing:** `retrieve_similar_tickets` pulls up to 1,000 docs then filters in Python. Fine at 4.5k docs; document the scaling limit and revisit if the corpus grows. | 🟢 |
| E5 | Re-validate the **parallel context fetch** (`ThreadPoolExecutor`, max 5) against current rate limits; ensure ordering/back-off still correct. | 🟢 |
| E6 | Produce a one-page **architecture diagram** (data flow: FS API → ingest → Chroma → search → rerank → UI → AI guidance) to anchor the README. | 🟡 |

**Deliverables:** shared session/client utilities, faster reingest, architecture diagram, before/after timing notes.
**Acceptance:** measurable reduction in session/client creation and reingest API calls; no behavior change.

---

## Phase 6 — Security & Secrets Audit  🟠

**Objective:** No secret leakage; no injection vectors; safe defaults.

| ID | Task | Severity |
|----|------|----------|
| S1 | **Secret-in-history scan:** confirm `api.env` was never committed (`git log --all -- api.env`) and scan history for keys (e.g. `gitleaks`/`trufflehog`). If anything leaked, rotate keys. | 🔴 |
| S2 | Confirm `.gitignore` covers all secret/log/data artifacts (it does today: `api.env`, `*.log`, `chroma_db/`); add `api.env.example` as the only committed env template. | 🟠 |
| S3 | **HTML injection / XSS:** `app.py` uses `unsafe_allow_html=True` with interpolated ticket data (subject, category path, group name, URLs). A malicious/odd ticket subject could inject markup. Escape interpolated values or render via safe components. | 🟠 |
| S4 | **URL construction:** ticket links built from env + ids; validate `FRESHSERVICE_TICKET_URL_TEMPLATE`/portal domain handling and avoid open-redirect-style surprises. | 🟢 |
| S5 | **Logging:** ensure response bodies logged (`resp.text[:200]`) and the guidance prompt log (`freshservice_debug.log`) never capture secrets/PII; gate verbose logs behind a flag (already partly done via `LOG_GUIDANCE_PROMPT`). | 🟡 |
| S6 | Document **secrets management for deployment** (Vault/1Password) — README already gestures at this; make it concrete. | 🟢 |

**Deliverables:** history-scan report, escaped UI rendering, secrets handling doc.
**Acceptance:** clean secret scan; no unescaped user-controlled HTML; verified key handling.

---

## Phase 7 — Testing, CI & Documentation  🟠

### 7a. Testing & CI
| ID | Task | Severity |
|----|------|----------|
| T1 | Add `pytest` (currently not installed) + config (`pyproject`/`pytest.ini`) and a `conftest.py`. | 🟠 |
| T2 | **Fix `tests/test_ai_summarizer.py`** — it hits the live OpenAI API, has no assertions, and burns credits. Convert to a mocked unit test. | 🟠 |
| T3 | Expand coverage for currently-untested core: `text_cleaning` (reply/sig/confidential stripping), `config.normalise_freshservice_domain`, `freshservice.sanitize_metadata`, `search_tickets._rerank_results`/`_bucket_by_percentile`, `agent_resolver` payload parsing (mocked). | 🟠 |
| T4 | Mock all external calls (Freshservice + OpenAI) so the suite runs offline and deterministically. | 🟠 |
| T5 | Add **CI** (GitHub Actions): install pinned deps, run `ruff`, run `pytest`. Optionally pre-commit hooks. | 🟡 |

### 7b. Documentation overhaul
The repo has **9 markdown files (~2,800 lines)** with heavy overlap and drift. Several are transient debugging/working notes for *completed* work.

| ID | Task | Severity |
|----|------|----------|
| W1 | **Consolidate.** Keep a lean set: `README.md` (overview/setup/usage), `USER_GUIDE.md`, `API_DOCUMENTATION.md`, `TROUBLESHOOTING.md`. **Archive or delete** transient notes: `REFACTORING_PLAN.md`, `REFACTORING_VERIFICATION.md`, `AI_GUIDANCE_DEBUG_TROUBLESHOOTING.md`, `PROMPT_DEBUG_GUIDE.md` (move to `docs/archive/` or remove). Fold `QUICK_REFERENCE.md` into the README or keep as the single cheat-sheet. | 🟠 |
| W2 | **Fix factual drift** across all docs: ticket count (claims **3,660** → actual **4,484**), version/date stamps ("January 2025", v2.1.0), and the project name (Nexus vs. Freshservice Semantic Search). | 🟠 |
| W3 | **Remove references to non-existent files/dirs:** `requirements.txt`, `api.env.example`, `ticket_images/`, `logs/` are cited but don't exist — either create them (Phase 1/2) or strike the references. | 🟠 |
| W4 | **Reconcile config values stated in docs vs. code:** e.g. default search distance (README says 0.55 in one place, 0.9 in another), `SEARCH_MAX_DISPLAY` (README "5" vs `config.py` 10), default collection name. One source of truth. | 🟠 |
| W5 | Rewrite **setup instructions** to match the Phase 1 outcome (exact install commands, data-bootstrap steps: ingest + generate `categories.json`). | 🟠 |
| W6 | Add the **architecture diagram** (E6) and a short **"How it works"** section. Add a `CHANGELOG.md` and a real `LICENSE` (README says "proprietary"). | 🟢 |
| W7 | Ensure **docstrings/inline comments match behavior** after refactors (Phases 3–5). | 🟢 |

**Deliverables:** offline-deterministic test suite, CI pipeline, consolidated/accurate docs, architecture diagram.
**Acceptance:** `pytest` green offline; docs contain zero references to missing files and zero stale stats.

---

## 4. Repo Hygiene (cross-cutting cleanup)

| ID | Task | Severity |
|----|------|----------|
| H1 | Remove local clutter from the working tree (gitignored but present): `.DS_Store`, `.cursor/debug.log`, `.start_app.log`, `freshservice_debug.log`. | 🟢 |
| H2 | Review `push_to_github.sh` — keep, document, or remove. | 🟢 |
| H3 | Confirm `__pycache__/`, `.venv/`, `chroma_db/` remain untracked (they are) and stay out of any future commits. | 🟢 |
| H4 | Decide whether `categories.json`/`raw_ticket_fields.json` should be committed (taxonomy is fairly static) or generated on setup — document the choice. | 🟡 |

---

## 5. Suggested Execution Order & Effort (rough)

| Order | Phase | Effort | Risk |
|------:|-------|:------:|:----:|
| 1 | Phase 0 — Baseline | 0.5 day | low |
| 2 | Phase 1 — Dependencies/runtime | 1–1.5 days | **high** (touches OpenAI+Chroma) |
| 3 | Phase 2 — Config & data | 1 day | med |
| 4 | Phase 3 — Correctness/bugs | 1 day | med |
| 5 | Phase 6 — Security | 0.5 day | low |
| 6 | Phase 4 — Quality/dead-code | 1–2 days | low |
| 7 | Phase 5 — Efficiency | 1 day | med |
| 8 | Phase 7 — Tests/CI/docs | 1.5–2 days | low |

**Total:** ~8–10 focused days. Phases 1–2 are the gate: until they're done, a fresh clone can't run and AI features are fragile.

---

## 6. Deliverables Summary

1. `requirements.txt` + `requirements-dev.txt` (pinned) and validated clean install.
2. Unified configuration (single canonical collection name + defaults) and `api.env.example`.
3. Generated/committed data files or a documented bootstrap (`categories.json`, optional `raw_ticket_fields.json`).
4. Bug-fix set (deprecated APIs removed, error paths hardened).
5. Leaner code: dead imports/functions removed, `app.py` decomposed, shared utils, lint/format config.
6. Efficiency improvements: shared HTTP session + cached Chroma client + faster reingest.
7. Security: clean secret scan, escaped HTML rendering, secrets-handling doc.
8. Offline test suite + CI.
9. Consolidated, factually-correct documentation + architecture diagram.

---

## 7. Decisions Needed Before Execution

1. **OpenAI SDK:** pin `openai<1.0` (low effort) **or** migrate to `openai>=1.x` (recommended, more work, must re-verify Chroma embeddings). *(D2)*
2. **Project name:** "Nexus" or "Freshservice Semantic Search"? *(Q6/W2)*
3. **Data files:** commit `categories.json` (+ raw) or generate on setup? *(G2/H4)*
4. **Doc strategy:** delete transient docs outright, or move them to `docs/archive/`? *(W1)*
5. **Packaging:** keep flat scripts, or move to a `src/` package + `pyproject.toml`? *(Q3/D1)*

---

## Appendix A — Head-Start Findings (already confirmed during planning)

These were verified while preparing this plan, so execution can start immediately.

**🔴 Critical**
- `requirements.txt` is referenced (README, `start_app.py:191`, `TROUBLESHOOTING.md`) but **does not exist**. Fresh installs break.
- Legacy OpenAI SDK calls (`openai.ChatCompletion`/`openai.Embedding`/`openai.api_key`/`message["content"]`) in `ai_recommendations.py:135-147`, `ai_summarizer.py:35-50`, `debug_utils.py:179-182`. Only work because `openai==0.28.1` is pinned in the venv — and nothing records that pin.
- `categories.json` **missing** → empty AI taxonomy + 11-token fallback (`search_context.py:51`, `search_intent.py:83`).
- Collection-name mismatch: `config.py:75` default `freshservice_core` vs. on-disk/used `FreshService` (`debug_utils.py:121`). App only works via `api.env` override.

**🟠 High**
- `st.experimental_rerun()` (removed in newer Streamlit) at `app.py:1141,1145`, inconsistent with `st.rerun()` elsewhere.
- `raw_ticket_fields.json` missing → `_status_choices()` dead-load fallback (`app.py:449`).
- `api.env.example` referenced by README but missing.
- Doc drift: README says **3,660** tickets / v2.1.0 / "January 2025"; actual collection has **4,484** docs.
- HTML-injection surface: `unsafe_allow_html=True` with interpolated ticket fields throughout `app.py`.

**🟡 Medium**
- Dead imports in `app.py:40-45`: `AIGuidance`, `SystemDiagnostics`, `handle_streamlit_error`, `safe_import`.
- `handle_streamlit_error` + `safe_import` in `debug_utils.py` defined but unused project-wide.
- Branding split: `app.py:131` title "Nexus" vs. docs.
- New `requests.Session` and new Chroma `PersistentClient`/embedding fn created per call (no reuse on CLI paths) despite README claiming reuse.
- `pytest` not installed; `tests/test_ai_summarizer.py` hits the live API with no assertions.
- 9 markdown docs (~2,800 lines) with heavy overlap; 4 are transient debug/refactor notes for completed work.
- Numeric inconsistencies between docs and `config.py` (search distance, `SEARCH_MAX_DISPLAY`, collection name).

**🟢 Low**
- Local clutter present (gitignored): `.DS_Store`, `.cursor/debug.log`, `.start_app.log`, `freshservice_debug.log`.
- README references `ticket_images/` and `logs/` directories that don't exist.
- `_extract_preview_text` carries an unresolved TODO about showing AI summaries.

## Appendix B — Referenced-but-missing files (verify/create/strike)
`requirements.txt` · `categories.json` · `raw_ticket_fields.json` · `api.env.example` · `ticket_images/` · `logs/`
