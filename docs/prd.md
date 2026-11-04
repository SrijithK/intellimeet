# Product Requirements Document

## 1. Product summary

IntelliMeet is a meeting intelligence assistant for teams that need fast answers from recorded or uploaded meeting transcripts. Users upload transcript files, ask questions about decisions, action items, and discussion topics, and receive grounded answers with citations to the meeting transcript.

## 2. Problem

Teams lose context across recurring meetings. Important decisions, owners, and follow-ups are spread across transcript history and difficult to search. The product should turn transcript archives into an answerable knowledge base without requiring users to manually read every meeting.

## 3. Target users

### Primary user: team lead / PM / engineering manager
- Reviews previous meetings for decisions and commitments.
- Wants to answer: “What did we decide about launch timing?” or “Who owns the rollout tasks?”
- Values low-friction workflow and trustworthy answers.

### Secondary user: project participant
- Needs quick recap of a past thread or unresolved action.
- Wants to trace a topic back to source transcript lines.

## 4. Core user journeys

1. Upload a transcript or add a seed transcript file.
2. Ingestion parses the file, chunks it by speaker turn, embeds content, and extracts decisions and action items.
3. User asks a question in natural language.
4. System retrieves relevant transcript windows and structured facts.
5. System returns a grounded answer with citations and references to the transcript.

## 5. Functional requirements

### 5.1 Transcript ingestion
- Accept `.txt` transcripts in the format `[hh:mm:ss] Speaker: text`.
- Accept WebVTT transcripts.
- Store a canonical transcript model: meeting + turns with speaker, start, end, text.
- Support seed-folder auto-ingestion on startup.
- Expose REST API for meeting upload and status tracking.
- Process ingestion asynchronously and surface status to the user.

### 5.2 Structured extraction
- Extract decisions from transcript text.
- Extract action items with owner, task, and due date when available.
- Extract discussion topics and link them to the relevant transcript turns.
- Persist metadata for speaker and timestamps.

### 5.3 Retrieval and answering
- Use hybrid retrieval: vector similarity + full-text matching.
- Filter by meeting, speaker, or date when relevant.
- Answer only from retrieved context and transcript evidence.
- Cite answers as `[meeting, timestamp, speaker]`.
- If no relevant evidence exists, explicitly say the system did not find supporting material.

### 5.4 User experience
- Provide a chat-like interface for Q&A.
- Show transcript context in meeting detail view.
- Support meeting list and search by title/date.
- Display action items and decisions per meeting.

## 6. Non-functional requirements

- Responses should be fast enough for a single interactive session.
- Answers must cite transcript evidence.
- Ingestion must be asynchronous and resilient.
- Data and metadata must remain in one relational store with pgvector.
- Local-first operation must work using Docker Compose.
- Cloud-ready architecture should be achievable without rewriting business logic.

## 7. Acceptance criteria

### Ingestion
- A transcript uploaded via the API is accepted and jobs are tracked by status.
- Seed folder transcripts are imported automatically during startup.
- Speaker timestamps and transcript text are preserved in a canonical model.

### Retrieval and answers
- Questions about decisions return answers grounded in transcript evidence.
- Questions about action items return owner and task context if present.
- When evidence is missing, the system responds honestly rather than guessing.

### UI
- User can select a meeting and view transcript detail.
- User can ask a question and receive a streamed answer.
- Answer text includes reference citations tied to transcript lines.

## 8. Out of scope (future work)
- Voice transcription and audio ingestion
- Zoom / Teams webhook integrations
- Multi-tenancy and auth
- Production cloud deployment details beyond an architecture-ready target

## 9. Success metrics
- High answer groundedness on decision and action-item questions.
- Users can find the source transcript line for every answer.
- Ingestion is idempotent and reproducible across repeated runs.
- Team can run the app locally with a single Docker Compose setup.
