# Architecture Blueprint

## 1. Overview

The system is structured as a decoupled frontend and Python backend. The backend owns parsing, ingestion, retrieval, extraction, and answer generation. The database stores both relational business data and vector/indexed transcript search data in one Postgres instance.

## 2. Component view

### Frontend
- React + TypeScript + Vite
- Tailwind + shadcn/ui
- Upload flow for meeting transcripts
- Meeting list, detail view, and chat interface
- Streams answers from the backend over SSE

### Backend API
- FastAPI service
- Exposes REST endpoints for meeting upload, job status, and chat queries
- Validates transcript input and orchestrates ingestion jobs
- Handles retrieval and answer generation calls

### Ingestion workers
- Async background job layer
- Accepts transcript files and creates canonical transcript records
- Runs parsing, chunking, embedding, extraction, and indexing
- Hides implementation behind a `JobQueue` interface

### Data layer
- Postgres with pgvector
- Stores meetings, turns, chunks, extracted decisions, action items, topics, and retrieval metadata
- Uses full-text search and vector search together via application-level fusion logic

### AI layer
- Embeddings: local `bge-small-en` via fastembed
- LLM answer generation: Claude Sonnet 5.5
- Lightweight extraction: Claude Haiku 4.5
- Provider access is abstracted behind interfaces

## 3. Core data model

### Meeting
- `id`
- `title`
- `source_type`
- `uploaded_at`
- `date`
- `media_uri` (nullable)

### TranscriptTurn
- `id`
- `meeting_id`
- `speaker`
- `start_ts`
- `end_ts`
- `text`

### TranscriptChunk
- `id`
- `meeting_id`
- `turn_id`
- `text`
- `embedding`
- `start_ts`
- `end_ts`

### Decision
- `id`
- `meeting_id`
- `turn_id`
- `summary`
- `decision_text`
- `confidence`

### ActionItem
- `id`
- `meeting_id`
- `turn_id`
- `owner`
- `task`
- `due_date`
- `status`

### Topic
- `id`
- `meeting_id`
- `turn_id`
- `label`

## 4. Ingestion pipeline

1. Intake transcript from upload or seed folder.
2. Select transcript parser by file type.
3. Parse into canonical `Meeting -> turns` object.
4. Chunk turns into sections with speaker/timestamp metadata.
5. Generate embeddings for each chunk.
6. Store chunks and metadata in Postgres.
7. Extract decisions, action items, and topics with LLM.
8. Persist structured records linked back to source turns.
9. Mark job complete and enable query access.

## 5. Retrieval strategy

The system uses hybrid retrieval:
- Vector similarity for semantic relevance
- Full-text search for names, ticket IDs, dates, and exact lexical matches
- Metadata filters by meeting, speaker, and date
- RRF fusion logic in application code to rank combined results

## 6. Answer generation

- Retrieve the most relevant evidence windows and structured facts.
- Build prompt context from transcript chunks and extracted data.
- Ask the answer model to respond using only the supplied evidence.
- Require answer citations in the format `[meeting, timestamp, speaker]`.
- If retrieval is empty, the assistant must say no relevant evidence was found.

## 7. Interface boundaries

The architecture intentionally isolates infrastructure behind interfaces:
- `JobQueue`
- `TranscriptSource`
- `LLMProvider`
- `Embedder`
- `FileStorage`

This keeps local development simple while allowing AWS replacements such as SQS, S3, Bedrock, or managed Postgres later without rewriting the application core.

## 8. Deployment target

### Local
- Docker Compose
- `frontend` (nginx serving the React build)
- `api` (FastAPI service)
- `postgres` (with pgvector)

### AWS-ready path
- CloudFront + WAF for frontend
- ALB + ECS Fargate for API
- S3 for files
- SQS + DLQ for async ingestion
- Aurora PostgreSQL with pgvector
- Bedrock for model access
- Cognito, Secrets Manager, and IAM roles for security

## 9. Non-goals for v1
- Live Zoom / Teams integrations
- Automatic audio transcription
- Multi-tenancy and auth
- Rich analytics beyond meeting-level summarization and task extraction
