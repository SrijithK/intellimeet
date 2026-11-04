# Delivery Plan and Story Map

## 1. Epic 0: Project setup and alignment

### Story 0.1: confirm product scope
- Objective: lock the MVP to transcript upload, retrieval, and grounded chat.
- Outcome: final decision document and project brief agreed.

### Story 0.2: create BMAD project artifacts
- Objective: create the requirement and architecture foundation.
- Outcome: PRD, architecture, and implementation plan are in place.

## 2. Epic 1: Backend foundation

### Story 1.1: define canonical transcript model
- Create Meeting and TranscriptTurn domain models.
- Support timestamped transcript text from `.txt` and VTT sources.

### Story 1.2: build ingestion API and job flow
- POST /api/meetings endpoint
- Async ingestion status tracking
- File source handling with pluggable parser registration

### Story 1.3: configure storage and vector database
- Postgres + pgvector schema for meetings, turns, chunks, decisions, and action items.
- Migration scripts for tables and indexes.

## 3. Epic 2: Retrieval and extraction

### Story 2.1: chunk and embed transcripts
- Chunk text by time-windowed turn groups.
- Generate embeddings with local fastembed model.
- Persist metadata for meeting/speaker/timestamp

### Story 2.2: hybrid retrieval
- Add full-text query support alongside vector search.
- Fuse results with RRF ranking.
- Filter by meeting, speaker, and date constraints.

### Story 2.3: structured extraction
- Extract decisions, action items, and topics from transcripts.
- Link extracted records back to the source turns.

## 4. Epic 3: Q&A and citations

### Story 3.1: chat API
- Accept user questions and retrieve relevant context.
- Return streamed responses to the UI.

### Story 3.2: grounded answer generation
- Use retrieved evidence and extracted structured facts only.
- Include citation format `[meeting, timestamp, speaker]`.
- Handle missing evidence with a transparent no-result response.

## 5. Epic 4: Frontend experience

### Story 4.1: meeting upload UX
- Upload transcript files through the UI.
- Show ingest job status and completion state.

### Story 4.2: meeting detail view
- Display transcript lines and metadata.
- Show decisions and action items in context.

### Story 4.3: chat experience
- Allow natural-language questions.
- Stream answers and display citations.

## 6. Epic 5: QA, hardening, and demo readiness

### Story 5.1: test coverage
- Backend unit tests for parser, chunking, retrieval, and answer logic.
- API integration tests for upload and chat endpoints.

### Story 5.2: golden-set evaluation
- Evaluate retrieval quality and answer grounding against a curated set of questions.
- Tune prompts and retrieval if quality misses expectations.

### Story 5.3: Docker + documentation
- Compose setup for local running
- README with setup, architecture notes, and local usage steps
- Demo-ready screenshots or short walkthrough

## 7. Definition of done

A story is done when:
- The feature works locally via Docker Compose.
- Tests cover the main behavior.
- Retrieval and answers are grounded in transcript evidence.
- The user can trace outputs back to the original meeting and timestamp.
- The feature aligns with documented product and architecture decisions.

## 8. Recommended delivery order

1. Project brief and architecture freeze
2. Backend data model and ingestion API
3. Retrieval and extraction pipeline
4. Grounded answer API
5. Frontend chat and meeting detail view
6. Validation, docs, and demo readiness
