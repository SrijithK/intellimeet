# IntelliMeet

Meeting intelligence assistant. Upload meeting transcripts, then ask questions about what was
discussed, decided and assigned. Every answer comes only from the transcripts and cites its
sources as `[meeting, hh:mm:ss, speaker]`. Each citation links to the exact transcript line.

Take-home assignment, Option 3: Meeting Intelligence System.

![Chat: a streamed answer with citations to transcript lines](docs/images/chat.png)

![Meeting view: extracted decisions and action items, with the cited line highlighted](docs/images/meeting.png)

## Contents

- [Quick start](#quick-start)
- [Ollama setup](#ollama-setup)
- [Using it](#using-it)
- [Architecture](#architecture)
- [API](#api)
- [Evaluation](#evaluation)
- [Local development](#local-development)
- [Configuration](#configuration)
- [Project layout](#project-layout)
- [Design decisions and trade-offs](#design-decisions-and-trade-offs)
- [Limitations and future work](#limitations-and-future-work)

## Quick start

**Prerequisites**

- Docker (Docker Desktop on macOS/Windows)
- Ollama running on the host with `llama3.1` pulled. See [Ollama setup](#ollama-setup); in short:

  ```bash
  ollama pull llama3.1
  curl http://localhost:11434/api/version   # should return {"version": "..."}
  ```

**Run**

```bash
docker compose up --build
```

| What | URL |
|---|---|
| App | http://localhost:8080 |
| API + Swagger UI | http://localhost:8001/docs |
| Postgres | `localhost:5433` (user/password/db: `intellimeet`) |

On first start the four sample transcripts in [`data/transcripts/`](data/transcripts) are
ingested automatically, which takes about 20 seconds including LLM extraction. Restarts don't
ingest them again.

Ports can be changed with `FRONTEND_PORT` and `API_PORT`, and the model with `OLLAMA_MODEL`, e.g.
`FRONTEND_PORT=3000 docker compose up`.

## Ollama setup

The LLM runs locally in [Ollama](https://ollama.com): no API key, and no data leaves the machine.
It runs on the host, not in a container: Docker on macOS can't use the Apple GPU, so a containerised
model would run on the CPU only and answer several times slower. The `api` container reaches the host's
Ollama at `host.docker.internal:11434`.

```
┌──────────────── Docker ────────────────┐
│  frontend (nginx) ──▶ api (FastAPI) ───┼──▶ host.docker.internal:11434
│                        │               │            │
│                     postgres           │            ▼
└────────────────────────────────────────┘    Ollama on the host (llama3.1)
```

**1. Install**

| OS | Install |
|---|---|
| macOS | Download the app from [ollama.com/download](https://ollama.com/download), or `brew install ollama` |
| Linux | `curl -fsSL https://ollama.com/install.sh \| sh` (installs a systemd service) |
| Windows | Installer from [ollama.com/download](https://ollama.com/download) |

**2. Start it.** The macOS and Windows apps start the server automatically (look for the menu-bar or
tray icon). Otherwise, run `ollama serve` in a terminal. It listens on port `11434`.

**3. Pull the model** (about 4.9 GB to download):

```bash
ollama pull llama3.1
```

**4. Check it works**

```bash
ollama list                                  # llama3.1:latest should be listed
curl http://localhost:11434/api/version      # {"version": "..."}
ollama run llama3.1 "Reply with one word: ready"
```

Once the app is running and you've asked a question, `ollama ps` shows the model loaded. The
`CONTEXT` column reads `8192`, the context size the app requests, and `PROCESSOR` shows whether it
runs on the GPU.

**Hardware.** `llama3.1` (8B, 4-bit) uses about 6 GB of memory with the 8k context. 16 GB of RAM
is comfortable. On Apple Silicon it runs on the GPU and answers start in about 2 seconds. On a
CPU-only machine, expect answers to take tens of seconds.

**Linux with Docker.** Ollama listens only on `127.0.0.1` by default, which containers can't reach.
Make it listen on all interfaces, then restart it:

```bash
sudo systemctl edit ollama.service      # add the two lines below, save
#   [Service]
#   Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama
```

Compose already maps `host.docker.internal` to the host on Linux (`extra_hosts: host-gateway`).
Docker Desktop on macOS and Windows needs none of this.

**Using a different model.** Any Ollama chat model works, because Ollama itself makes the model's
extraction output match the JSON schema. Answer and extraction quality vary by model. Pull the
model and set `OLLAMA_MODEL`:

```bash
ollama pull qwen2.5:7b
OLLAMA_MODEL=qwen2.5:7b docker compose up -d api
```

The golden-set numbers in this README were measured with `llama3.1`. Re-run the
[evaluation](#evaluation) after switching models.

**Troubleshooting**

| Symptom | Cause and fix |
|---|---|
| Uploads show "Searchable, but extraction failed". Chat shows "Could not reach Ollama". | Ollama isn't running, or (on Linux) isn't reachable from Docker. Start it and check with `curl http://localhost:11434/api/version`. To reach it from inside the container: `docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/version').read())"` |
| `Ollama returned 404: {"error":"model 'llama3.1' not found"}` | The model isn't pulled: `ollama pull llama3.1` (or whatever `OLLAMA_MODEL` names). |
| The first answer after a while is slow | Ollama unloads idle models after about 5 minutes, and reloading takes a few seconds. Later answers are fast. |
| Answers are very slow | The model is running on the CPU. Check the `PROCESSOR` column in `ollama ps`. |

Meetings ingested while Ollama was down stay searchable, but have no extracted decisions or action
items. There's no retry button yet (see [Limitations](#limitations-and-future-work)). The only
way to re-extract is a fresh database: `docker compose down -v && docker compose up`. This also
removes uploaded meetings; the sample transcripts are ingested again on startup.

## Using it

1. **Upload** `.txt` or `.vtt` transcripts from the sidebar (drag and drop, several at once). Each
   upload shows its ingestion status. Supported formats:
   - Plain text, one turn per line: `[hh:mm:ss] Speaker: text`. Lines without a timestamp continue
     the previous turn.
   - WebVTT, including Zoom exports (numbered cues) and Teams exports (`<v Speaker>` voice tags).
2. **Open a meeting** to see the transcript and its extracted decisions, action items (owner, task,
   due date) and topics. Click any of them to jump to the line it came from.
3. **Ask questions** across all meetings, or scope a question to one meeting. Answers stream in.
   Each citation links to the exact transcript line, and the "sources" list quotes them. If the
   transcripts don't contain the answer, the app says so instead of guessing.

Example questions for the sample data:

- *Why was the launch moved, and what's the new date?*
- *What action items does Aisha have?*
- *What problems have been reported with the bank connection step?* (spans two meetings)
- *What is the marketing budget for Q1?* (not in the transcripts: answered as not found)

## Architecture

```mermaid
flowchart LR
    subgraph Browser
        UI["React SPA<br/>(Vite, Tailwind, shadcn/ui)"]
    end
    subgraph Docker Compose
        NGINX["frontend<br/>nginx: static files,<br/>proxies /api (SSE unbuffered)"]
        API["api<br/>FastAPI"]
        PG[("postgres<br/>pgvector + full-text")]
    end
    OLLAMA["Ollama on host<br/>llama3.1"]
    EMB["bge-small-en-v1.5<br/>(ONNX, in the api image)"]

    UI --> NGINX --> API
    API --> PG
    API --> OLLAMA
    API --- EMB
```

### Ingestion (asynchronous job)

```mermaid
flowchart LR
    F[".txt / .vtt upload<br/>or seed folder"] --> P["Parse<br/>(TranscriptSource registry)"]
    P --> M["Canonical model<br/>Meeting → turns<br/>speaker, start, end, text"]
    M --> C["Chunk<br/>~90 s windows of whole turns,<br/>1-turn overlap"]
    C --> E["Embed<br/>bge-small, 384-d"]
    E --> S[("meetings, turns, chunks<br/>vector + tsvector")]
    S --> X["Extract with LLM<br/>decisions, action items, topics<br/>each linked to its source turn"]
    X --> S2[("decisions, action_items, topics")]
```

- Every input format is parsed into one canonical model. Chunking, embedding, extraction and chat
  only see that model, so adding a format means writing a parser and registering it.
- Uploads return a job ID immediately. The job runs behind a `JobQueue` interface (in-process
  asyncio today). Identical files are recognised by content hash and not processed twice.
- The meeting becomes searchable before extraction runs. If extraction fails (for example, Ollama
  is down), the meeting is marked `extraction_status: failed` but stays searchable.
- Extraction output is validated: items that cite a turn that doesn't exist, or have empty fields,
  are dropped.

### Answering a question

```mermaid
sequenceDiagram
    participant UI
    participant API
    participant DB as Postgres
    participant LLM as Ollama
    UI->>API: POST /api/chat {question, filters}
    API->>DB: vector search (top 20) + full-text search (top 20)
    API->>API: Reciprocal Rank Fusion → top 6 chunks
    API->>DB: turns for those chunks + extracted decisions / action items
    alt nothing relevant (similarity, keyword and owner checks)
        API-->>UI: "not found" (LLM not called)
    else
        API->>LLM: numbered transcript lines + facts + question
        LLM-->>API: streamed tokens citing [n]
        API-->>UI: SSE: citations, tokens with [n] → [meeting, hh:mm:ss, speaker], done
    end
    API->>DB: query log (question, chunks, citations, tokens, latency)
```

- **Hybrid retrieval:** pgvector cosine similarity plus Postgres full-text search, merged with
  Reciprocal Rank Fusion in our own code. Results can be filtered by meeting, speaker and date.
- **Citations:** the model only sees short reference numbers like `[7]` and cites those. The
  server rewrites them into `[meeting, hh:mm:ss, speaker]` while streaming and drops any number
  that isn't in the evidence. Small local models copy a number reliably; they don't reliably copy
  a three-part citation.
- **Structured facts:** extracted decisions and action items are added to the evidence, each
  citing its source line. Action items of a person named in the question ("what does Aisha
  owe?") are included from every meeting.
- **Not found:** a cheap check skips the LLM when nothing relevant was retrieved. Beyond that, the
  prompt tells the model to reply with a fixed sentence when the evidence doesn't answer the
  question.

### Data model

```mermaid
erDiagram
    meetings ||--o{ turns : has
    meetings ||--o{ chunks : has
    turns ||--o{ decisions : "source of"
    turns ||--o{ action_items : "source of"
    turns ||--o{ topics : "source of"
    meetings {
        string id
        string title
        string source_type "txt, vtt (audio later)"
        string media_uri "nullable, for voice"
        string content_hash
        string extraction_status
    }
    turns {
        int idx
        string speaker
        float start_ts
        float end_ts
        text text
    }
    chunks {
        int first_turn_idx
        int last_turn_idx
        string_list speakers
        vector embedding "384-d, HNSW"
        tsvector tsv "generated, GIN"
    }
    action_items {
        int turn_idx
        string owner
        text task
        string due
    }
```

`jobs` (ingestion status) and `queries` (one row per chat request) are separate tables. The
schema is managed by Alembic migrations.

## API

The full contract is [`docs/openapi.json`](docs/openapi.json) (OpenAPI 3.1). It's generated from
the code, and a test fails if the two drift apart. The running API also serves it as Swagger UI
at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/meetings` | Upload a transcript (multipart). Returns `{job_id, status}`. |
| `GET` | `/api/jobs/{job_id}` | Ingestion job status and result |
| `GET` | `/api/meetings` | List meetings |
| `GET` | `/api/meetings/{id}` | Transcript, decisions, action items, topics |
| `GET` | `/api/search?q=…` | Hybrid search, for inspecting retrieval (ranks, similarity) |
| `POST` | `/api/chat` | Ask a question. The response is a Server-Sent Events stream. |
| `GET` | `/health` | Liveness |

`/api/chat` streams these events: `citations` (sources the answer may cite), repeated `token`
events (answer text, citations already rendered), then `done` (full answer, cited sources, token
counts, latency, `query_id`) or `error`.

```bash
curl -N -X POST localhost:8001/api/chat -H 'Content-Type: application/json' \
  -d '{"question": "What action items does Aisha have?"}'
```

## Evaluation

A golden set of 39 questions about the sample meetings
([`backend/evaluation/golden_set.json`](backend/evaluation/golden_set.json)):
- decisions, action items, facts and "why" questions
- questions spanning meetings, a reworded question and a meeting-scoped question
- 5 questions the transcripts can't answer
- 10 **held-out** cases, written after all tuning and never tuned against, over a deliberately messy
  transcript ([`northwind-pilot-sync.vtt`](data/transcripts/northwind-pilot-sync.vtt): filler words,
  crosstalk, a speaker label that changes, a missing speaker, spoken numbers, a self-correction, a
  decision reversed in the same meeting, a long monologue, and an instruction aimed at an AI
  assistant), plus 3 near-miss questions that sound answerable but aren't

Each case lists the transcript lines that support the answer and the key facts it must contain.

A case **passes** when all of these hold:
- an answerable question is answered (not "not found")
- the answer cites at least one expected line
- the answer contains every key fact (citations are removed before this check)
- the answer contains none of the forbidden text (used to catch an obeyed prompt injection)

An unanswerable question passes when the reply is "not found".

Latest run ([full report](backend/evaluation/results/latest.md)), `llama3.1` 8B on Ollama:

| Metric | Result |
|---|---|
| Expected line in the top 6 retrieved chunks | 31 / 31 (MRR 0.898) |
| Answer passes (found, correct citation, key facts) | 31 / 31 |
| Answerable questions wrongly declined | 0 / 31 |
| Unanswerable questions declined | 6 / 8 |
| Prompt injection obeyed | 0 / 2 |
| Pass rate: tuned set, held-out set | 29 / 29, 8 / 10 |
| Median answer latency | 3.4 s |

**The tuned-set numbers are optimistic**: those transcripts, questions and prompt adjustments were
written together. The held-out set is the more honest signal. Its two failures are both near-miss
questions:
- *"What is the Starter tier price for beta customers?"* was answered with the general Starter price
  ($12). Only the Team tier has a beta price, so the model combined two true facts into a false one.
- *"How many support tickets complained about the slow mobile app?"* got "a few complaints, much
  smaller volume", with a citation. No number was invented, so this is arguably a good answer that
  the binary found / not-found scoring marks as a failure.

```bash
cd backend
.venv/bin/python -m evaluation.run_eval          # own database (intellimeet_eval), needs Ollama
.venv/bin/python -m evaluation.run_eval --reuse  # skip re-ingestion
```

The retrieval-only part runs in the normal test suite with no LLM needed, and fails if fewer than
90% of questions retrieve an expected line.

## Local development

Postgres from Compose, with the API and frontend run directly:

```bash
docker compose up -d postgres

# Backend (Python 3.9+; the container uses 3.12)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
API_TARGET=http://localhost:8000 npm run dev     # http://localhost:5173
```

Checks:

| | Command |
|---|---|
| Backend tests (real Postgres, auto-creates `intellimeet_test`) | `cd backend && .venv/bin/python -m pytest -q` |
| Include the live LLM test | `RUN_LLM_TESTS=1 .venv/bin/python -m pytest -q` |
| Backend lint/format | `.venv/bin/ruff check . && .venv/bin/ruff format --check .` |
| Migrations match models | `.venv/bin/alembic check` |
| Frontend tests | `cd frontend && npm test` |
| Frontend typecheck, lint, build | `npm run typecheck && npm run lint && npm run build` |

After changing the API:
1. Regenerate the contract: `cd backend && .venv/bin/python -m scripts.export_openapi`
2. Regenerate the frontend types: `cd frontend && npm run gen:api`

Current suites: backend 89 tests (plus 1 live-LLM test that only runs on request), frontend 20.

## Configuration

Environment variables (see [`.env.example`](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://intellimeet:intellimeet@localhost:5433/intellimeet` | Postgres |
| `LLM_PROVIDER` | `ollama` | LLM backend (behind the `LLMProvider` interface) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server (`host.docker.internal` in Compose) |
| `OLLAMA_MODEL` | `llama3.1` | Model for extraction and answers |
| `OLLAMA_NUM_CTX` | `8192` | Context window. Ollama silently truncates input longer than this. |
| `EXTRACTION_ENABLED` | `true` | Turn LLM extraction off (meetings stay searchable) |
| `SEED_DIR` | unset | Folder ingested on startup (Compose mounts `data/transcripts`) |
| `LOG_LEVEL` | `INFO` | Application log level |
| `TEST_DATABASE_URL` / `EVAL_DATABASE_URL` | `…/intellimeet_test`, `…/intellimeet_eval` | Test and evaluation databases |

## Project layout

```
docker-compose.yml        postgres, api, frontend
data/transcripts/         sample transcripts (seeded on startup; used by tests and the eval)
docs/                     PRD, architecture, decisions, stories, openapi.json, images
backend/
  app/main.py             FastAPI routes
  app/schemas.py          API request/response models (the contract)
  app/models.py           canonical Meeting / TranscriptTurn / TranscriptChunk
  app/parsers/            TranscriptSource registry, txt and vtt parsers
  app/llm/                LLMProvider interface, Ollama provider
  app/services/           ingestion, chunking, embedder, extraction, retrieval,
                          answering, query_log, job_queue, job_store, meeting_store, seeding
  migrations/             Alembic
  evaluation/             golden set, scoring, runner, latest results
  tests/                  pytest
frontend/
  src/api/                typed client (types generated from the contract), SSE reader
  src/pages/              chat, meeting detail
  src/components/         layout, upload, meeting list, citations; ui/ is shadcn-generated
```

## Design decisions and trade-offs

<!--
  To be written by the author, in their own words. Raw notes with the options considered are in
  docs/decisions.md. Suggested prompts are kept below as comments.
-->

### Problem framing and scope

<!-- Why Option 3; what a user of this needs; what was deliberately left out. -->

_TODO_

### Stack

<!-- FastAPI + React; Postgres + pgvector instead of a separate vector DB; no LangChain/LlamaIndex. -->

_TODO_

### Retrieval and grounding

<!-- Turn-window chunking; hybrid search + RRF; structured extraction at ingestion; turn-level
     citations via reference numbers; the two-layer "not found" design. -->

_TODO_

### LLM choice: local Ollama instead of the Anthropic API

<!-- The original plan (D3) and why it changed; what that costs in quality and speed; how the
     LLMProvider interface keeps the switch to Claude / Bedrock a configuration change. -->

_TODO_

### Path to production on AWS

<!-- From D10: SQS, S3, Bedrock, Aurora + pgvector, ECS Fargate, Cognito, and so on; what's
     already behind interfaces. -->

_TODO_

### How AI tools were used

<!-- How the work was split with the AI assistant; what was reviewed, changed or rejected. -->

_TODO_

## Limitations and future work

Known limitations, observed while building and testing:

- **Each question is answered independently.** There is no conversation memory, so follow-ups like
  "and who owns that?" don't work.
- **Small local model.** `llama3.1` 8B occasionally misses an implied commitment during extraction.
  For example, "I'm adding retries with exponential backoff" is not always recorded as an action
  item. Answer latency depends on the host machine.
- **Evaluation is small** (see [Evaluation](#evaluation)): 39 cases, 10 of them held out. Scoring
  is substring-based, so it can't credit a correct "it wasn't specified" answer or check every
  claim for faithfulness; an LLM judge would add that.
- **Near-miss questions can get confidently wrong answers.** When the evidence holds related facts
  (the Starter price, the Team beta price), the model can combine them into an answer nobody gave.
- **Speaker names aren't merged.** "Priya" and "Priya S." in the same transcript are two speakers
  and two action-item owners, so the speaker filter and the owner lookup only match the exact label.
- **No sense of meeting order across meetings.** Seeded transcripts have no meeting date, so if a
  later meeting reversed an earlier decision, the model couldn't tell which one is current.
- **"Not found" judgement is a heuristic.** Similarity alone can't separate short answerable
  questions from unanswerable ones, so a keyword match also counts as relevant, and the model's
  own "not found" reply is the second check.
- **Due dates are stored as spoken** ("by Friday"), not as real dates, because transcripts carry
  no meeting date yet.
- **Re-uploading after a failed extraction doesn't retry the extraction.**
- **Single API process.** The in-process job queue means one worker. Scaling out needs a real
  queue behind the `JobQueue` interface.
- **Observability:** every query is stored in the database with its retrieved chunks, citations,
  token counts and latency. Structured JSON logs and request IDs are not done yet.

Out of scope for this version:

- Voice input (speech-to-text, e.g. Amazon Transcribe). The schema already has
  `meetings.source_type` and `media_uri` for it.
- Zoom/Teams webhooks for automatic transcript import
- Authentication and multi-tenancy
- AWS deployment
- An Anthropic/Bedrock `LLMProvider` (the interface is in place)
