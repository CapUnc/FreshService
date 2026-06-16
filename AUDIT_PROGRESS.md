# 🛠️ Nexus Audit — Execution Progress Tracker

> **Resume pointer for a new session:** read this file top-to-bottom, then continue
> from the first unchecked item under "Current status". All work happens on the
> `audit/cleanup` branch. The full plan with task IDs lives in [AUDIT_PLAN.md](AUDIT_PLAN.md).

## Locked decisions (from the user)
1. **OpenAI** → migrate to `openai>=1.x` **and** add an in-app **model picker** (user selects the model).
2. **Project name** → **Nexus** (rebrand everything).
3. **`categories.json`** → **generate on setup** (do not commit; document the bootstrap step).
4. **Transient docs** → **delete** (REFACTORING_PLAN, REFACTORING_VERIFICATION, AI_GUIDANCE_DEBUG_TROUBLESHOOTING, PROMPT_DEBUG_GUIDE).
5. **Packaging** → **keep flat** for now (no `src/` package / pyproject move yet).
6. **Database** → the user authorized wiping all currently-synced data (previous-job data; will re-sync different data later).

## Working agreements
- Branch: `audit/cleanup`. Commit in coherent, working checkpoints. **Do not push** without explicit ask.
- Keep each commit in a runnable state. No valid Freshservice/OpenAI creds available for live calls (previous-job keys), so verify via imports + unit tests, not live API.
- Update this file at the end of every checkpoint.

---

## Current status: **Checkpoints A, C, B done. Next: Checkpoint D (correctness: `st.experimental_rerun` → `st.rerun`, etc.).**

### ✅ / ⬜ Checkpoints
- 🔄 **A — Foundations** (in progress)
  - [x] Branch `audit/cleanup` created
  - [x] `requirements.lock.txt` (known-good freeze) captured
  - [x] `requirements.txt` + `requirements-dev.txt` authored
  - [x] `api.env.example` authored
  - [x] Removed dead imports in `app.py` (AIGuidance, SystemDiagnostics, handle_streamlit_error, safe_import)
  - [x] Deleted 4 transient docs
  - [x] Removed local clutter (.DS_Store, .cursor/debug.log, *.log)
  - [x] Wiped `chroma_db/` (user-authorized)
  - [x] Smoke-test: all modules compile + import; offline tests run (see Findings #1)
  - [x] Commit A
- ✅ **B — Nexus rebrand + config unification** (done — committed)
  - [x] Rebranded "Freshservice Semantic Search" → "Nexus" across code (`app.py` page title, `start_app.py` banners, `debug_utils.py`) and all user docs. (Kept "Freshservice" where it means the actual product/API. `AUDIT_PLAN.md` intentionally retains the old name as it documents the inconsistency.)
  - [x] Unified Chroma collection default → `nexus_tickets` in `config.py` and `debug_utils.py` (matches `api.env.example`)
  - [x] Fixed README factual drift: removed stale ticket stats (3,660), `ticket_images/`, `January 2025`/`v2.1.0`; documented model picker + `OPENAI_AVAILABLE_MODELS`; corrected file/structure refs
  - [ ] **Deferred to H:** deep rewrite of USER_GUIDE / QUICK_REFERENCE / TROUBLESHOOTING / API_DOCUMENTATION (only titles rebranded so far; stats/examples there still need updating) + architecture diagram
  - [ ] **Deferred (low pri):** rename `freshservice_debug.log` file (gitignored; written by `debug_utils.py` + `ai_recommendations.py`)
  - [ ] **User action:** when re-syncing, set `CHROMA_COLLECTION_NAME=nexus_tickets` in your `api.env` (or remove the override to use the new default). I did not edit your real `api.env`.
- ✅ **C — OpenAI 1.x migration + model picker** (done — committed)
  - [x] Pin `openai>=1.50,<2` (NOT 2.x: chromadb 0.4.22's embedding fn only detects the `1.x` client via `version.startswith("1.")`; under 2.x it falls back to the removed `openai.Embedding` and ingestion would crash). Installed 1.109.1.
  - [x] Migrated `ai_recommendations.py`, `ai_summarizer.py`, `debug_utils.py` to the modern `OpenAI()` client (`chat.completions.create` / `embeddings.create`, `.message.content`)
  - [x] Added shared `config.openai_client()` + `config.available_models()` (env `OPENAI_AVAILABLE_MODELS`)
  - [x] Added sidebar "🧠 AI model" selectbox; threaded `selected_model` into guidance + seed-summary calls (`generate_guidance(model=...)`, `build_seed_text_from_ticket(summary_model=...)`)
  - [x] Removed dead `handle_streamlit_error` / `safe_import` from `debug_utils.py`
  - [x] Verified: Chroma `OpenAIEmbeddingFunction` v1 path = True; mocked-client test of guidance + summary passes
- 🔄 **D — Correctness fixes** (Phase 3)
  - [x] `st.experimental_rerun()` → `st.rerun()` (2x in `_render_empty_state`; the old API is removed in current Streamlit and would crash the "Allow other…" buttons)
  - [ ] Error-path review (broad `except` / RerunException handling)
  - [ ] Agent-resolution N+1 API calls (`_resolve_assigned_agent`)
  - [ ] Ticket-update field-name verification
- ⬜ **E — Efficiency** (Phase 5): shared session/client reuse, faster reingest
- ⬜ **F — Security** (Phase 6): HTML/XSS escaping, secret-history scan
- ⬜ **G — Tests/CI** (Phase 7a): mock external calls, expand coverage, CI
- ⬜ **H — Docs overhaul** (Phase 7b): consolidate + rewrite to match reality, architecture diagram

---

## 🔎 Findings discovered during execution
1. **Stale/broken unit tests (pre-existing).** `tests/test_search_intent.py` has 2 failing tests,
   undetected because pytest was never installed and there is no CI:
   - `test_extract_query_intent_detects_known_tokens` asserts `"access" in intent.keywords`, but
     `"access"` is in `_STOPWORDS` (`search_intent.py`), so it is intentionally excluded.
   - `test_annotate_result_with_tokens_matches_text_and_metadata` expects `category_match=True` from a
     free-text query, but `category_match` only fires when `intent.category` is set (i.e. from seed
     metadata), which this test never provides.
   → **Decision needed in Checkpoint G:** are these wrong tests (fix the assertions) or a missing
     feature (derive category from free-text query against the taxonomy)? Treat as test/impl drift;
     do not weaken assertions blindly. The 3 tests in `test_relevance_filters.py` pass.

## Changelog (most recent first)
- _Checkpoint B_: rebranded the project to **Nexus** across code + docs; unified the Chroma
  collection default to `nexus_tickets`; fixed README factual drift (stale stats, dead file
  refs, version/date) and documented the model picker.
- _Checkpoint C_: migrated to modern OpenAI SDK (`openai>=1.50,<2`, installed 1.109.1) across
  `ai_recommendations`, `ai_summarizer`, `debug_utils`; added shared `openai_client()` +
  `available_models()` in config; added in-app model picker wired into guidance + summaries;
  removed 2 dead helpers from `debug_utils`. Verified via mocked client (no live API).
- _Checkpoint A_: foundations — pinned deps (`requirements*.txt` + lock), `api.env.example`,
  removed dead imports in `app.py`, deleted 4 transient docs, removed local clutter, wiped `chroma_db/`,
  added `AUDIT_PLAN.md` + this tracker. Discovered Finding #1.
