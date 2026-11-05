from app.parsers.text import parse_txt_transcript
from app.parsers.vtt import parse_vtt_transcript


def test_parse_txt_transcript_extracts_turns_and_timestamps():
    transcript = """[00:01:05] Alice: We decided to move the launch.
[00:02:10] Bob: I will own the rollout checklist.
"""

    meeting = parse_txt_transcript("demo.txt", transcript)

    assert meeting.title == "demo"
    assert len(meeting.turns) == 2
    assert meeting.turns[0].speaker == "Alice"
    assert meeting.turns[0].start == 65
    assert meeting.turns[1].speaker == "Bob"
    assert meeting.turns[1].start == 130
    assert meeting.turns[1].text == "I will own the rollout checklist."


def test_parse_vtt_transcript_handles_cue_blocks():
    transcript = """WEBVTT

00:00:01.000 --> 00:00:05.500
Alice: Thanks for the update.

00:00:06.000 --> 00:00:09.000
Bob: We'll keep the action item open.
"""

    meeting = parse_vtt_transcript("demo.vtt", transcript)

    assert meeting.title == "demo"
    assert len(meeting.turns) == 2
    assert meeting.turns[0].speaker == "Alice"
    assert meeting.turns[1].speaker == "Bob"
    assert meeting.turns[1].text == "We'll keep the action item open."


def test_registry_picks_parser_by_extension_and_sets_source_type():
    import pytest

    from app.parsers import parse_transcript, supported_extensions

    assert {"txt", "vtt"} <= supported_extensions()
    meeting = parse_transcript("Demo.VTT", "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nAlice: Hi\n")
    assert meeting.source_type == "vtt"
    with pytest.raises(ValueError, match="Unsupported file type: md"):
        parse_transcript("notes.md", "# hi")
