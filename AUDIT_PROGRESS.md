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

## Current status: **Checkpoint A in progress**

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
- ⬜ **B — Nexus rebrand + config unification**
  - [ ] Rename app title / docs / log file names to Nexus
  - [ ] Unify Chroma collection default (`config.py` `freshservice_core` → `nexus_tickets`); align `debug_utils.py`
  - [ ] Fix doc factual drift (ticket counts, version/date, file references)
- ⬜ **C — OpenAI 1.x migration + model picker**
  - [ ] Bump `openai` to 1.x in requirements
  - [ ] Migrate `ai_recommendations.py`, `ai_summarizer.py`, `debug_utils.py` to `OpenAI()` client
  - [ ] Add `config.available_models()` + sidebar model selector wired into guidance/summarizer
  - [ ] Remove dead `handle_streamlit_error` / `safe_import` from `debug_utils.py`
  - [ ] Verify ingestion/search still construct (Chroma `OpenAIEmbeddingFunction` auto-handles v1)
- ⬜ **D — Correctness fixes** (Phase 3): `st.experimental_rerun` → `st.rerun`, error-path review, agent N+1
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
- _Checkpoint A_: foundations — pinned deps (`requirements*.txt` + lock), `api.env.example`,
  removed dead imports in `app.py`, deleted 4 transient docs, removed local clutter, wiped `chroma_db/`,
  added `AUDIT_PLAN.md` + this tracker. Discovered Finding #1.
