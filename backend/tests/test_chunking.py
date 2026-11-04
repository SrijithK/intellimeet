from app.models import Meeting, TranscriptTurn
from app.services.chunking import chunk_meeting
from app.services.embedder import LocalEmbedder


def test_chunk_meeting_groups_turns_by_window():
    meeting = Meeting(
        title="demo",
        source_name="demo.txt",
        turns=[
            TranscriptTurn(speaker="Alice", text="We decided to move the launch.", start=5, end=20),
            TranscriptTurn(speaker="Alice", text="The rollout starts next Friday.", start=21, end=40),
            TranscriptTurn(speaker="Bob", text="I will own the action items.", start=41, end=55),
        ],
    )

    chunks = chunk_meeting(meeting, max_turns=2, max_chars=180)

    assert len(chunks) == 2
    assert chunks[0].speaker == "Alice"
    assert "launch" in chunks[0].text
    assert chunks[1].speaker == "Bob"
    assert chunks[1].start == 41


def test_embedder_returns_stable_vector_for_text():
    embedder = LocalEmbedder()
    vector = embedder.embed_text("We decided to move the launch.")

    assert len(vector) == 8
    assert all(isinstance(value, float) for value in vector)
    assert vector == embedder.embed_text("We decided to move the launch.")
