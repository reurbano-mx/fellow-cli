import json
import sys
from io import StringIO

import pytest

from fellowai.output import emit, render_action_item_card, render_recording_markdown


def _capture(monkeypatch: pytest.MonkeyPatch, isatty: bool) -> StringIO:
    buf = StringIO()
    buf.isatty = lambda: isatty  # type: ignore[method-assign]
    monkeypatch.setattr(sys, "stdout", buf)
    return buf


def test_list_piped_emits_json(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=False)
    emit([{"id": "a"}, {"id": "b"}], shape="list", columns=["id"])
    assert json.loads(buf.getvalue()) == [{"id": "a"}, {"id": "b"}]


def test_list_tty_emits_table(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=True)
    emit([{"id": "a", "name": "Alpha"}], shape="list", columns=["id", "name"])
    out = buf.getvalue()
    assert "id" in out and "name" in out and "Alpha" in out


def test_force_json_flag(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=True)
    emit([{"id": "a"}], shape="list", columns=["id"], format_override="json")
    assert json.loads(buf.getvalue()) == [{"id": "a"}]


def test_force_md_flag(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=False)
    rec = {"id": "x", "title": "T", "started_at": "2026-05-01T00:00:00Z", "ended_at": None,
           "transcript": None, "ai_notes": None}
    emit(rec, shape="document",
         markdown_renderer=lambda d: render_recording_markdown(d),
         format_override="md")
    out = buf.getvalue()
    assert "# T" in out


def test_empty_list_tty_friendly(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=True)
    emit([], shape="list", columns=["id"], empty_message="No recordings.")
    assert "No recordings." in buf.getvalue()


def test_empty_list_piped_emits_empty_array(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=False)
    emit([], shape="list", columns=["id"])
    assert json.loads(buf.getvalue()) == []


def test_render_recording_markdown_with_transcript():
    rec = {
        "id": "r1",
        "title": "Test Meeting",
        "started_at": "2026-05-01T10:00:00Z",
        "ended_at": "2026-05-01T10:30:00Z",
        "transcript": {
            "speech_segments": [
                {"start": 0.0, "end": 2.5, "speaker": "Alice", "text": "Hello."},
                {"start": 2.5, "end": 5.0, "speaker": "Bob", "text": "Hi back."},
            ],
            "language_code": "en",
        },
        "ai_notes": None,
    }
    md = render_recording_markdown(rec)
    assert "# Test Meeting" in md
    assert "[Alice]: Hello." in md
    assert "[Bob]: Hi back." in md


def test_render_recording_markdown_with_ai_notes():
    rec = {
        "id": "r1", "title": "T", "started_at": "2026-05-01T00:00:00Z", "ended_at": None,
        "transcript": None,
        "ai_notes": [{
            "id": "n1", "title": "AI Notes", "is_active": True, "template_creator": "fellow",
            "sections": [
                {"title": "Summary", "type": "STANDARD", "content": "We discussed plans."},
                {"title": "Decisions", "type": "STANDARD",
                 "content": [{"text": "Ship by Friday."}, {"text": "Hire one more."}]},
            ],
        }],
    }
    md = render_recording_markdown(rec)
    assert "## Summary" in md and "We discussed plans." in md
    assert "## Decisions" in md and "Ship by Friday." in md


def test_render_action_item_card():
    item = {
        "id": "x", "text": "Do thing",
        "status": "Incomplete",
        "due_date": "2026-06-01",
        "assignees": [{"full_name": "Alice", "email": "a@x.com"}],
        "ai_detected": True,
    }
    card = render_action_item_card(item)
    assert "Do thing" in card and "Incomplete" in card and "Alice" in card
