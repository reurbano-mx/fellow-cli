import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from fellowai.cli import cli


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FELLOWAI_SUBDOMAIN", "test")
    monkeypatch.setenv("FELLOWAI_API_KEY", "k")


def test_list_notes_json(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.notes.FellowClient") as MockClient:
        MockClient.return_value.list_notes.return_value = iter([
            {"id": "n1", "title": "Note A", "event_start": "2026-05-01T00:00:00Z"},
        ])
        result = runner.invoke(cli, ["notes", "list", "--since", "7d", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["id"] == "n1"


def test_list_notes_passes_filter(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.notes.FellowClient") as MockClient:
        MockClient.return_value.list_notes.return_value = iter([])
        runner.invoke(cli, ["notes", "list", "--since", "2026-05-01", "--with-content", "--json"])
    kwargs = MockClient.return_value.list_notes.call_args.kwargs
    assert kwargs["filters"]["created_at_start"] == "2026-05-01T00:00:00Z"
    assert kwargs["include"]["content_markdown"] is True


def test_get_note_markdown(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.notes.FellowClient") as MockClient:
        MockClient.return_value.get_note.return_value = {
            "id": "n1", "title": "Standup",
            "event_start": "2026-05-01T10:00:00Z", "event_end": "2026-05-01T10:30:00Z",
            "event_attendees": [{"email": "a@x.com"}],
            "content_markdown": "# Agenda\n- Item 1",
        }
        result = runner.invoke(cli, ["notes", "get", "n1"])
    assert result.exit_code == 0
    assert "# Standup" in result.output
    assert "a@x.com" in result.output
    assert "Agenda" in result.output


def test_export_notes_to_dir(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    outdir = tmp_path / "out"
    runner = CliRunner()
    with patch("fellowai.commands.notes.FellowClient") as MockClient:
        MockClient.return_value.list_notes.return_value = iter([
            {"id": "n1", "title": "One", "event_attendees": None,
             "content_markdown": "body"},
        ])
        result = runner.invoke(
            cli, ["notes", "export", "--with-content", "--format", "md", "--to", str(outdir)]
        )
    assert result.exit_code == 0
    assert (outdir / "n1.md").exists()
