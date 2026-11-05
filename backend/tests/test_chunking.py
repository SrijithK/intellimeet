from app.models import Meeting, TranscriptTurn
from app.services.chunking import chunk_meeting


def _meeting(*turns):
    return Meeting(
        title="demo",
        source_name="demo.txt",
        turns=[TranscriptTurn(speaker=s, text=t, start=start) for s, t, start in turns],
    )


def test_short_meeting_is_a_single_chunk_with_all_speakers():
    meeting = _meeting(
        ("Alice", "We decided to move the launch.", 5),
        ("Bob", "I will own the rollout checklist.", 21),
        ("Alice", "Great, thanks.", 40),
    )

    chunks = chunk_meeting(meeting)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.speakers == ["Alice", "Bob"]
    assert (chunk.first_turn_idx, chunk.last_turn_idx) == (0, 2)
    assert chunk.text.splitlines() == [
        "Alice: We decided to move the launch.",
        "Bob: I will own the rollout checklist.",
        "Alice: Great, thanks.",
    ]
    assert (chunk.start, chunk.end) == (5, 40)


def test_time_window_splits_chunks_with_one_turn_overlap():
    meeting = _meeting(
        ("Alice", "Intro.", 0),
        ("Bob", "Budget update.", 30),
        ("Carol", "Hiring update.", 60),
        ("Alice", "Launch moved.", 100),  # >90s after turn 0, so a new window starts
        ("Bob", "Agreed.", 120),
    )

    chunks = chunk_meeting(meeting, window_seconds=90)

    assert [(c.first_turn_idx, c.last_turn_idx) for c in chunks] == [(0, 2), (2, 4)]
    assert chunks[1].speakers == ["Carol", "Alice", "Bob"]
    assert chunks[1].start == 60


def test_char_limit_splits_chunks():
    meeting = _meeting(*[("Alice", "x" * 40, i) for i in range(6)])

    chunks = chunk_meeting(meeting, max_chars=100)  # "Alice: " + 40 chars = 47 per line, two fit

    assert [(c.first_turn_idx, c.last_turn_idx) for c in chunks] == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    assert all(len(c.text) <= 100 for c in chunks)


def test_oversized_turn_becomes_its_own_chunk_without_overlap():
    meeting = _meeting(
        ("Alice", "short", 0),
        ("Bob", "y" * 500, 10),
        ("Carol", "short", 20),
    )

    chunks = chunk_meeting(meeting, max_chars=100)

    assert [(c.first_turn_idx, c.last_turn_idx) for c in chunks] == [(0, 0), (1, 1), (2, 2)]


def test_empty_turns_are_skipped_but_indices_refer_to_original_turns():
    meeting = _meeting(("Alice", "   ", 0), ("Bob", "Hello", 5))

    chunks = chunk_meeting(meeting)

    assert len(chunks) == 1
    assert (chunks[0].first_turn_idx, chunks[0].speakers) == (1, ["Bob"])


def test_empty_meeting_has_no_chunks():
    assert chunk_meeting(_meeting()) == []
