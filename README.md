# Project Governance Brain

An AI-powered meeting intelligence platform that turns raw meeting transcripts
into an **organizational memory**. Transcripts are ingested into a knowledge
graph and a vector store (the **GBrain** memory layer); questions are answered by
retrieving evidence from that memory and reasoning over it with **Hermes**.

```
Raw meeting → Transcript → Knowledge graph + Vector memory
            → Context retrieval → Hermes reasoning → Human-like answer
```

The design follows one rule above all: **storage, retrieval, and reasoning are
separate**. GBrain stores and retrieves but never answers. Hermes reasons but
never stores. The only external intelligence dependency is Hermes, and it is the
only thing that is configurable.

---

## Architecture

```
Frontend (React/TS/Tailwind)
      │
      ▼
FastAPI backend ── routes ── services ── repositories ── PostgreSQL / SQLite
      │                        │
      │                        ├── GBrain  (memory: chunk → entity → graph → vector)
      │                        └── Hermes  (reasoning: prompt → LLM → answer)
      ▼
Knowledge graph + Vector memory
```

Every cross-layer dependency is expressed as an interface (`AbstractGBrain`,
`AbstractVectorStore`, `HermesClient`), and the whole object graph is assembled
in one composition root (`backend/app/core/dependencies.py`). That keeps the
system SOLID and every piece independently testable.

### Request flow

- **Ingestion** (`POST /meetings/upload`): raw persistence → `gbrain.ingest()`
  runs chunking, entity extraction, graph extraction and vector indexing →
  action items derived from ownership edges.
- **Query** (`POST /chat`): `gbrain.search()` fuses graph + vector evidence into
  a `RAGContext` → `hermes.answer()` reasons over it → grounded answer plus the
  evidence used.

---

## Persistence, editing, theming & Outlook

**Persistent data.** The structured store (SQLite by default, Postgres in
production) persists to disk. The local vector index is rebuilt from the
database automatically on startup, so semantic search survives restarts with no
re-ingestion. With Qdrant, vectors persist independently.

To use Postgres, set `DATABASE_URL` in `backend/.env` (see `.env.example`) and
restart — `docker compose up` already provisions a Postgres service.

**Secrets in `.env`.** Database URL/password, Hermes keys, and Microsoft 365
credentials are all read through `app/core/config.py` from environment / `.env`.
Nothing is hard-coded. Start from `.env.example`.

**Delete & edit meetings.**

| Endpoint | Action |
|----------|--------|
| `DELETE /meetings/{id}` | Forget a meeting (DB rows + vectors) |
| `PATCH /meetings/{id}` | Edit title/duration, or `append_transcript` / replace `transcript` — memory is rebuilt automatically |

In the UI: delete from a meeting card (trash icon on hover) or the detail page;
edit via the **Edit** button on the detail page (rename, or append transcript).

**Dark / light theme.** Toggle with the sun/moon button in the top bar. The
choice is saved and respects your OS preference on first load.

**Outlook mail + Teams (Microsoft Graph).** Once configured, the chat box can
drive email:

- *"fetch my last 3 mails"* → lists recent inbox messages
- *"send an email to sam@example.com saying the report is ready"* → sends it

Setup: create an Azure AD app registration, add a client secret, grant
**application** permissions (admin consent) `Mail.Read`, `Mail.Send` (and
`Chat.ReadWrite` for Teams), then fill `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`,
`GRAPH_CLIENT_SECRET`, `GRAPH_DEFAULT_USER` in `backend/.env`. Until then, mail
commands return a friendly setup message and everything else works normally.

---

## Weekly / per-meeting reports (PDF)

The reporting module turns memory into a downloadable status report with a
grounded **merits & demerits** assessment. Every merit and demerit is backed by
a real signal — an ownership edge, an action-item status, or a progress/blocker
cue found in the transcript — so reports are meaningful even on the offline
`local` reasoner. With a real LLM configured, the executive summary is enriched
by Hermes.

Endpoints:

| Endpoint | Returns |
|----------|---------|
| `GET /reports/meeting/{id}` | PDF for one meeting |
| `GET /reports/meeting/{id}/preview` | JSON preview |
| `GET /reports/weekly?date=YYYY-MM-DD` | PDF for the week containing that date (defaults to today) |
| `GET /reports/weekly/preview?date=YYYY-MM-DD` | JSON preview |

In the UI, open the **Reports** tab, pick *Weekly* (with a date) or *By meeting*,
hit **Preview** to see it on screen, or **Download PDF**. Examples:

```bash
curl -OJ localhost:8000/reports/meeting/M003                # per-meeting PDF
curl -OJ "localhost:8000/reports/weekly?date=2026-06-21"    # weekly PDF
```

The PDF includes a stat strip, executive summary, merits, demerits (each with
evidence quotes), a responsibilities table, an action-item table, and the list
of meetings covered. PDF generation uses reportlab (pure Python, no system
libraries).

---

## Running it

### Option A — local, zero infrastructure

The defaults use SQLite, an in-process vector index, and an offline deterministic
reasoner, so nothing external is required.

```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000  (docs at /docs)

# frontend (separate terminal)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

Try it:

```bash
curl -X POST localhost:8000/meetings/upload -H 'Content-Type: application/json' \
  -d '{"meeting_id":"M001","title":"Sprint Meeting","transcript":"Alice:\nAPI development should finish this week.\n\nBob:\nAuthentication module is pending.\n\nCharlie:\nI'\''ll complete testing."}'

curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"query":"What task was assigned to Bob?"}'
# → "Bob is responsible for Authentication."
```

### Option B — full stack with Docker

```bash
cd docker
docker compose up --build
# frontend → http://localhost:3000   backend → http://localhost:8000
```

This brings up the backend, the built frontend (nginx), PostgreSQL and Qdrant.

---

## Configuring Hermes (the only intelligence dependency)

Set `HERMES_PROVIDER` (see `.env.example`). No business logic changes between
providers — only this setting and its connection details.

| Provider | What it does | Extra config |
|----------|--------------|--------------|
| `local`  | Deterministic offline reasoning over retrieved evidence (dev/CI) | none |
| `hermes` | The real installed Hermes service over HTTP | `HERMES_BASE_URL`, `HERMES_API_KEY` |
| `hermes_cli` | A locally-installed Hermes CLI agent, run per query | `HERMES_CLI_PATH`, `HERMES_CLI_ARGS` |
| `hermes_api` | Hermes Agent's built-in API server (OpenAI-compatible, agentic) | `HERMES_BASE_URL`, `HERMES_API_KEY`, `HERMES_MODEL` |
| `openai` | Any OpenAI-compatible `/v1/chat/completions` endpoint | `HERMES_BASE_URL`, `HERMES_API_KEY`, `HERMES_MODEL` |
| `ollama` | A local Ollama server | `HERMES_BASE_URL`, `HERMES_MODEL` |

To add another LLM, write a `HermesClient` subclass in
`services/hermes/hermes_service.py` and register it in `build_hermes_service`.

If a remote provider call fails, the service falls back to the local reasoner so
the app stays responsive.

## Contact section (Gmail / Outlook / Teams / Calendar via Composio)

The **Contact** page connects the app to your email and calendar through
[Composio](https://composio.dev), which manages the OAuth connections and tools.

1. In the Composio dashboard, connect the accounts you want (Gmail, Outlook,
   Teams).
2. Put your key in `backend/.env` (never commit it):

   ```
   COMPOSIO_API_KEY=ak_your_key_here
   COMPOSIO_ENTITY_ID=default
   ```

3. `pip install composio-core` (already in `requirements.txt`) and restart.

Then the Contact page can list connected accounts, fetch and send email, and
list calendar events. Endpoints: `/comms/status`, `/comms/emails`, `/comms/send`,
`/comms/events`, `/comms/execute`, and `/comms/actions?app=<app>` to discover the
exact action slugs your account exposes. Action slugs are configurable in `.env`
(`COMPOSIO_GMAIL_FETCH`, `COMPOSIO_OUTLOOK_SEND`, …) — if a default doesn't match
your dashboard, override it there or look it up via `/comms/actions`.

Security: the key is read from the environment only; it is never hard-coded or
committed. If a key is ever exposed, rotate it in the Composio dashboard.

### Connecting to the Hermes API server (recommended)

Hermes Agent can expose an OpenAI-compatible API server. Enable it once:

```
hermes config set API_SERVER_ENABLED true
hermes config set API_SERVER_KEY your-secret-key
hermes gateway stop && hermes gateway      # listens on 127.0.0.1:8642
```

Verify: `curl http://127.0.0.1:8642/health` returns `{"status":"ok"}`. Then point
the app at it (note: no `/v1` suffix — the client appends it):

```
HERMES_PROVIDER=hermes_api
HERMES_BASE_URL=http://127.0.0.1:8642
HERMES_API_KEY=your-secret-key
HERMES_MODEL=hermes-agent
HERMES_AGENTIC=true
```

This is the most robust integration: no process spawning, no terminal scraping,
and Hermes runs as a full agent (its own memory + tools) for every chat message.

### Connecting a local Hermes CLI (e.g. the Nous Research agent)

That Hermes is an *agent* with its own memory (`gbrain`) and tools (`composio`
for email). There are two ways to connect it.

**Recommended — the API Server gateway.** Hermes can run a built-in HTTP API
designed for frontends. Set it up once:

```
hermes gateway setup        # enable the "API Server" platform
```

Then point the app at it (adjust the path/fields to the gateway's contract):

```
HERMES_PROVIDER=hermes_gateway
HERMES_GATEWAY_URL=http://localhost:8765
HERMES_GATEWAY_PATH=/chat
HERMES_GATEWAY_MESSAGE_FIELD=message
HERMES_GATEWAY_RESPONSE_FIELD=response
HERMES_AGENTIC=true
```

This returns clean JSON, keeps sessions, and avoids spawning a process per
message — the robust choice.

**Alternative — the CLI per query.** If you'd rather shell out, use the
single-shot flag `hermes chat -q "..."`:

```
HERMES_PROVIDER=hermes_cli
HERMES_CLI_PATH=hermes
HERMES_CLI_USE_STDIN=false
HERMES_CLI_ARGS=chat -q {prompt}
HERMES_AGENTIC=true
```

`{prompt}` becomes the question; the answer is returned with the TUI box/ANSI
chrome stripped. In **agentic** mode the question is passed verbatim so Hermes
does its own retrieval and tools — e.g. *"fetch my last 3 mails"* is answered by
Hermes via composio. If it blocks on tool-approval prompts when head-less,
append `--yolo` to `HERMES_CLI_ARGS` (bypasses approvals — use with care).

---

## Swapping the memory backends

- **Structured store**: point `DATABASE_URL` at PostgreSQL. The repository layer
  is the only code that touches the database.
- **Vector store**: `LocalVectorStore` (numpy, in-process) ships by default.
  Implement `AbstractVectorStore` for Qdrant / Chroma / PGVector and register it
  in `services/gbrain/vector_service.py::build_vector_store`, then set
  `VECTOR_BACKEND`.
- **Extraction**: the chunker and the entity/graph extractors are heuristic,
  dependency-free stand-ins for the installed GBrain's models. Replace them with
  GBrain's implementations — callers depend only on the `Abstract*` interfaces,
  so nothing else changes.

---

## Tests

```bash
pip install -r backend/requirements.txt
python -m pytest tests/ -q
```

Covers the ingestion pipeline, the chat/retrieval flow, and each GBrain
component in isolation.

---

## Layout

```
backend/app/
  api/            route handlers (meetings, chat, dashboard)
  core/           config, database, composition root
  models/         SQLAlchemy ORM
  schemas/        Pydantic request/response + RAGContext
  repositories/   the only code that reads/writes the DB
  services/
    gbrain/       chunking, entities, graph, vectors, retrieval, engine
    hermes/       prompt builder + provider adapters
    ingestion/    write-path orchestration
    chat/         read-path orchestration
frontend/src/     React app (pages, components, api client)
docker/           Dockerfiles, compose, nginx
tests/            pytest suite
```

---

## Future: multi-agent via GStack

The service interfaces are agent-ready. GStack workflows can orchestrate
multiple specialized agents (e.g. a retrieval agent, a verification agent, a
summarization agent) over the same GBrain memory and Hermes reasoning, without
changing the storage or retrieval contracts.
