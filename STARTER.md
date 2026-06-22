# 🚀 Nexus — Project Starter / Handoff

> **Read this first** (human or AI agent). It explains what this project is, its
> current state, the in-progress **Zendesk migration**, the two hard constraints
> (PII + messy data), and the recommended next step. Deeper history lives in
> [`AUDIT_PLAN.md`](AUDIT_PLAN.md) and [`AUDIT_PROGRESS.md`](AUDIT_PROGRESS.md).

## 1. What this is (30 seconds)
**Nexus** is a semantic-search + AI-guidance tool over historical support tickets.
An agent opens a tough ticket; Nexus finds the most similar *past* tickets **by
meaning** (not keywords) and an AI writes a short "what to do next" briefing built
from how those similar tickets were actually resolved. Stack: **Streamlit** UI,
**ChromaDB** vector store, **OpenAI** embeddings + LLM. Runs locally for now.

## 2. Current state
- Fully audited and modernized — pinned deps, modern OpenAI SDK, in-app model
  picker, security hardening, **29 tests, ruff-clean, GitHub Actions CI**. All on `main`.
- It currently speaks the **Freshservice** API. **The company uses Zendesk**, so the
  active goal is porting it to Zendesk.

## 3. The pivot: Freshservice → Zendesk
Nexus has two layers — only the second one changes:
- **The brain (platform-agnostic, keep as-is):** semantic search, ranking/bucketing,
  AI guidance, text cleaning, the UI. Files: `search_intent.py`, `text_cleaning.py`,
  `ai_recommendations.py`, `ai_summarizer.py`, `improved_ai_prompt.py`, ranking in `search_tickets.py`.
- **The connector (Freshservice-specific, needs a Zendesk version):** `config.py`
  (base URL / session / ticket links), `freshservice.py` (ingestion), `agent_resolver.py`
  (`/agents`, `/groups`), `search_context.py` (`/tickets?include=conversations`), plus the
  ticket-fetch in `search_tickets.py` and the unassigned-fetch / `_update_ticket_fields` /
  groups calls in `app.py`.

## 4. What we have to work with
- ✅ **A Zendesk API token** (goes in `api.env` — see §8). This unlocks ticket
  **descriptions + comments, including internal/agent notes** — exactly what Nexus needs.
- 📄 A one-time **CSV export** was analyzed (the export folders are git-ignored, contain
  **PII**, and are **not** in the repo). Key finding: **the CSV export is metadata-only —
  it has subjects but NO comment/description bodies.** So the **API is the real data source.**
  Reference stats from the export: ~7,694 tickets/month, **~3,238 solved/closed**, 16 agents,
  mostly email channel, statuses `New/Open/Pending/Hold/Solved/Closed`, `type` mostly blank.

## 5. Two hard constraints — read carefully

### A. PII scrubbing — must BUILD and must VERIFY
- **There is no real PII redactor today.** `text_cleaning.py` only strips signatures,
  reply chains, and legal footers. Inline emails / phone numbers / names / addresses /
  account numbers in the ticket body **pass straight through.**
- A redaction layer must run at **every point text leaves for OpenAI**: (1) before
  embedding at ingest, (2) before sending similar-ticket notes to the guidance model.
  Defense-in-depth: scrub before storing in the local index too.
- **Approach:** regex baseline (emails, phones, IPs, SSNs, card-like numbers, URLs) **+**
  a name/org deny-list built from `users.csv` / `organizations.csv`. Upgrade path:
  Microsoft **Presidio** (ML NER) for free-form names/addresses.
- **Must be unit-tested AND eyeballed raw→scrubbed on real tickets before we trust it.**
- Pair with **Azure OpenAI / a no-training agreement** as defense in depth.

### B. Inconsistent / sparse documentation
Many tickets are thin or have no write-up. Strategy:
- **Use every signal**, not just the body: subject + description + public comments +
  internal notes + tags + form + mapped custom fields.
- **Quality-gate the index:** only index tickets that actually have resolution content;
  report coverage (e.g. "of 3,238 solved, N have usable text"). Don't let empty tickets pollute results.
- **AI-normalize at ingest** (existing summarizer) to smooth inconsistent writing — only
  when there's content; never invent a resolution.
- **Honest guidance:** when the closest tickets have no notes, say so and fall back to
  routing / who-handled-it. (The prompt already supports this.)
- **Re-ingest** as the team's documentation improves.

## 6. Recommended FIRST step (read-only; de-risks both constraints)
A spike script that:
1. connects to Zendesk with the token,
2. pulls a sample of **solved/closed tickets with their comments + internal notes**,
3. runs the candidate **PII scrubber**, and
4. reports **content-quality stats** (how many have usable bodies/notes vs. empty) and
   prints **raw→scrubbed examples** for human verification.

No writes to Zendesk, no changes to the app's behavior — just evidence on "is PII handled"
and "is the data good enough" before committing to a full ingest pipeline.

**After the spike:** build the Zendesk connector (config + ingest + agent/group resolution
+ ticket fetch), wire the PII scrubber into the egress points, and re-point the
category/routing feature at Zendesk **forms/tags/custom-fields** (pull field labels from
`/api/v2/ticket_fields`).

## 7. Zendesk API quick reference
- **Auth:** HTTP Basic, username `"{email}/token"`, password = the API token.
  Base URL: `https://{subdomain}.zendesk.com/api/v2`.
- **Tickets:** `GET /tickets`, `/tickets/{id}`; **comments (incl. private notes):**
  `/tickets/{id}/comments`; bulk: `/incremental/tickets` (can sideload comments).
- **Users:** `/users/{id}` (role = agent / end-user / admin). **Groups:** `/groups/{id}`.
  **Fields:** `/ticket_fields`. **Forms:** `/ticket_forms`.
- **Statuses:** `new/open/pending/hold/solved/closed` (+ custom statuses). The
  "knowledge base" = **solved + closed**.

## 8. Environment (put real values in `api.env` — git-ignored, never commit)
```
# Zendesk (migration target)
ZENDESK_SUBDOMAIN=...
ZENDESK_EMAIL=...
ZENDESK_API_TOKEN=...

# OpenAI
OPENAI_API_KEY=...
OPENAI_GUIDANCE_MODEL=gpt-4o-mini

# Chroma
CHROMA_COLLECTION_NAME=nexus_tickets
```
See `api.env.example` for the full template. Existing `FRESHSERVICE_*` vars stay until the port is done.

## 9. Setup on a new machine
```bash
git clone git@github.com:CapUnc/FreshService.git
cd FreshService
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # or requirements-dev.txt for tests+lint
cp api.env.example api.env             # then fill in real keys
pytest                                  # 29 tests should pass
```
Do **not** copy `.venv/`, `chroma_db/`, `api.env`, or the export folders — recreate them.
The PII-laden ticket exports are intentionally **not** in the repo; pull fresh data via the API.

## 10. Gotcha to remember
`openai` is pinned **`>=1.50,<2`** on purpose — chromadb 0.4.22's embedding function only
recognizes the `1.x` client. Don't bump to 2.x without upgrading chromadb (see AUDIT_PROGRESS.md).
