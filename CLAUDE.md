# IntelliMeet

Meeting intelligence assistant: ingest meeting transcripts (speaker labels + timestamps) and answer
questions about discussions, decisions and action items using RAG. Built as a take-home assignment
(Option 3, "Meeting Intelligence System"). Time budget: 2 days.

Decision record with reasoning: [docs/decisions.md](docs/decisions.md). Read it before proposing
changes to the stack or architecture.

## Status

- Stack and architecture: finalised.
- Folder structure, modules, build/test commands: not yet defined. Update this file when they are.
- Nothing is built yet. Do not scaffold or write application code until the user says go.

## Stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript (Vite), Tailwind, shadcn/ui; streaming answers over SSE |
| Backend | Python, FastAPI, SQLAlchemy/SQLModel, Alembic migrations |
| Data | Postgres + pgvector (vectors, full-text `tsvector`, relational tables in one DB) |
| LLM | Claude via Anthropic API: `claude-sonnet-5-5` for answers, `claude-haiku-4-5` for ingestion-time extraction |
| Embeddings | Local `bge-small-en` via fastembed (ONNX, no PyTorch) |
| Orchestration | No framework: Anthropic SDK + our own retrieval/prompt code |
| Quality | pytest, Vitest, golden-set retrieval/answer eval, GitHub Actions CI |
| Observability | Structured JSON logs, request IDs, per-query tokens/latency/retrieved chunks persisted |
| Packaging | Docker Compose: `frontend` (nginx), `api`, `postgres` |

## Architecture rules

- **One canonical transcript model.** Every input is parsed into `Meeting -> turns[speaker, start, end, text]`.
  Chunking, embedding, extraction and chat only see this model.
- **Pluggable sources.** Each input format is a `TranscriptSource` registered by file type
  (`.txt`, `.vtt` now; audio later). Adding a format must not touch downstream code.
- **Ingestion is an async job with status**, even for text. Hide the mechanism behind a `JobQueue`
  interface (in-process locally, SQS on AWS).
- **Infra behind interfaces**: job queue, file storage, LLM provider, embedder. Swapping to AWS
  (SQS, S3, Bedrock) must be config, not a rewrite.
- **Hybrid retrieval**: pgvector similarity + Postgres full-text, fused (RRF) in our code, with
  metadata filters (meeting, speaker, date).
- **Structured extraction at ingestion**: decisions, action items (owner, task, due), topics stored
  in tables, each linked to source turn/timestamp.
- **Answers must cite** `[meeting, timestamp, speaker]`. If retrieval finds nothing relevant, say so;
  never answer from model knowledge.
- Schema leaves room for voice: `meetings.source_type`, nullable `meetings.media_uri`.

## Scope

- In: text transcripts (`.txt` with `[hh:mm:ss] Speaker: text`, WebVTT), UI upload, seed folder
  auto-ingested on startup, REST API.
- Out (document in README as future work): voice/Amazon Transcribe, Zoom/Teams webhooks, auth,
  multi-tenancy, AWS deployment.

## Working agreements for AI-assisted development

- Discuss and agree on design before writing code; build step by step.
- Keep it simple: a solid basic solution over a complex one. No speculative abstractions beyond the
  interfaces listed above.
- Every module gets tests alongside it. Run tests and lint before calling something done.
- No secrets in code or git; config via environment variables (`.env.example` documents them).
- The README's reasoning sections are written by the user in their own words. Claude may draft
  structure, diagrams and factual setup steps only.
