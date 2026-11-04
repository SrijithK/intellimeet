# Decision record

Decisions agreed during design, with the options considered. Raw notes for the README; the README's
reasoning sections will be rewritten in my own words.

## D1. Use case: Option 3, Meeting Intelligence System

Analyse meeting transcripts (speaker labels + timestamps) and answer questions about discussions,
decisions and action items.

## D2. Overall stack: Python AI service + React frontend

- **Considered:** (A) React + FastAPI, (B) all TypeScript (Next.js + Node), (C) React + Spring Boot / Spring AI.
- **Chosen:** A.
- **Why:** Python has the strongest ecosystem for the parts being evaluated (local embeddings,
  evals, future speech-to-text). Clean separation between UI and AI service. All three are within
  my experience; B would mean one language but weaker AI tooling, C is slower to iterate on.

## D3. LLM: Claude via the Anthropic API

- **Considered:** Anthropic API, Amazon Bedrock, supporting both.
- **Chosen:** Anthropic API locally; Bedrock is the production path on AWS.
- **Models:** Sonnet 5.5 for answering; Haiku 4.5 for cheaper ingestion-time extraction.
- **Why:** One env var to run locally. Bedrock gives the same models with IAM auth and data staying
  in AWS, so the provider sits behind an interface.

## D4. Retrieval store: Postgres + pgvector

- **Considered:** Elasticsearch, ChromaDB, MySQL + Chroma, Postgres + pgvector. (MySQL alone ruled
  out: Community edition has a `VECTOR` type but no vector index.)
- **Chosen:** Postgres + pgvector, replacing MySQL for structured data too.
- **Why:**
  - Hybrid search matters for meetings: names, ticket IDs, dates need keyword matching that pure
    vector search misses. Postgres does vector + full-text in one DB, joined with metadata.
  - One container instead of two; no keeping two stores in sync; one transaction per ingest.
  - Elasticsearch has the best hybrid search but needs 1-2 GB RAM and more config.
  - Chroma is light but has no ranked keyword search, so hybrid needs extra glue code.
  - Clear production path: Aurora PostgreSQL / RDS with pgvector.

## D5. Embeddings: local model via fastembed

- **Chosen:** `bge-small-en` via fastembed (ONNX runtime).
- **Considered:** Voyage AI, Amazon Titan Embeddings.
- **Why:** No extra API key, works offline, small Docker image (no PyTorch). Swapping later means
  re-embedding all chunks.

## D6. Orchestration: no framework

- **Considered:** LangChain, LlamaIndex.
- **Chosen:** Anthropic SDK + our own retrieval and prompt code.
- **Why:** Small, testable, easy to explain. The pipeline is simple enough that a framework adds
  more abstraction than value.

## D7. Product design: RAG plus structured extraction

- At ingestion, chunk by speaker turns grouped into time windows, with speaker/timestamp metadata.
- One-time LLM extraction of decisions, action items (owner, task, due) and topics into tables.
- "Who committed to what" questions use structured data; open questions use hybrid retrieval.
- Every answer cites `[meeting, timestamp, speaker]`, clickable to the transcript line.

## D8. Transcript input: upload, seed folder, API; no live integrations

- **Inputs:** drag-and-drop upload in the UI; `./data/transcripts` auto-ingested on startup
  (idempotent); `POST /api/meetings`.
- **Formats:** `.txt` (`[hh:mm:ss] Speaker: text`) and WebVTT (what Zoom/Teams/Meet export).
- **Not doing Zoom/Teams integration:** needs an OAuth app, a paid Zoom plan with cloud recording,
  and a public HTTPS webhook endpoint. Reviewers couldn't test it. Production design: webhook ->
  API Gateway -> SQS -> ingestion worker, reusing the same pipeline.
- **Sample data:** 4-5 synthetic transcripts for one fictional team over several weeks, with
  storylines that span meetings (a decision later reversed, action items carried over).

## D9. Voice: out of scope, designed for

- **Options assessed:** local faster-whisper (free, but no speaker labels without pyannote/PyTorch)
  vs Amazon Transcribe (built-in speaker labels; ~$0.024/min, 60 free min/month on the legacy free
  tier).
- **Chosen:** text only now. Future: Amazon Transcribe behind a feature flag.
- **Designed for it now:** canonical transcript model, pluggable sources, async ingestion jobs,
  `source_type` / `media_uri` columns.

## D10. Local-first, cloud-ready deployment

- **Local:** Docker Compose with `frontend` (nginx + React build, proxies `/api`), `api` (FastAPI,
  in-process ingestion jobs), `postgres` (pgvector).
- **AWS target:** CloudFront + WAF -> S3 (SPA) and ALB -> ECS Fargate API; S3 presigned uploads ->
  SQS (+DLQ) -> ECS Fargate worker; Aurora PostgreSQL Serverless v2 + pgvector via RDS Proxy;
  Bedrock via VPC endpoint; Cognito; Secrets Manager, KMS, IAM task roles; CloudWatch + X-Ray;
  AWS CDK; GitHub Actions -> ECR -> ECS.
- **Why local:** free to run, and reviewers reproduce it with `docker compose up` and one API key.
  Same container images run on ECS; infra sits behind interfaces, so moving to AWS is config and IaC,
  not a rewrite.

## D11. Time budget: 2 days

- **Day 1:** backend: parsers, chunking, embeddings, hybrid retrieval, extraction, chat API with
  streaming + citations, sample data, Docker Compose.
- **Day 2:** UI (library, meeting detail, chat), tests + golden-set eval, observability, README,
  screenshots/video.
- **Cut if short on time:** LLM tracing UI (Phoenix), talk-time/topic charts, cross-meeting action
  board (fallback: filtered table).
