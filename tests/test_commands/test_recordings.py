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


def test_list_recordings_pipes_json(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([
            {"id": "r1", "title": "T", "started_at": "2026-05-01T00:00:00Z"},
        ])
        result = runner.invoke(cli, ["recordings", "list", "--since", "7d", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["id"] == "r1"


def test_list_recordings_passes_since_filter(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([])
        runner.invoke(cli, ["recordings", "list", "--since", "2026-05-01", "--json"])
    call_kwargs = MockClient.return_value.list_recordings.call_args.kwargs
    assert call_kwargs["filters"]["created_at_start"] == "2026-05-01T00:00:00Z"


def test_list_recordings_with_transcript(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([])
        runner.invoke(cli, ["recordings", "list", "--with-transcript", "--json"])
    kwargs = MockClient.return_value.list_recordings.call_args.kwargs
    assert kwargs["include"]["transcript"] is True


def test_get_recording_outputs_markdown_by_default(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.FellowClient") as MockClient:
        MockClient.return_value.get_recording.return_value = {
            "id": "r1", "title": "Q2 planning",
            "started_at": "2026-05-01T00:00:00Z", "ended_at": None,
            "transcript": {"speech_segments": [
                {"start": 0.0, "end": 1.0, "speaker": "Alice", "text": "Hi"}
            ], "language_code": "en"},
            "ai_notes": None,
        }
        result = runner.invoke(cli, ["recordings", "get", "r1"])
    assert result.exit_code == 0
    assert "# Q2 planning" in result.output
    assert "[Alice]: Hi" in result.output


def test_with_media_null_emits_stderr_warning(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    # mix_stderr was removed in Click 8.4+; check combined output instead
    runner = CliRunner()
    with patch("fellowai.commands.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([
            {"id": "r1", "title": "T", "media_url": None}
        ])
        result = runner.invoke(
            cli, ["recordings", "list", "--with-media", "--json"]
        )
    assert result.exit_code == 0
    combined = result.output + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
    assert "not privileged" in combined


def test_export_to_stdout_concatenates_markdown(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([
            {"id": "r1", "title": "One", "started_at": None, "ended_at": None,
             "transcript": None, "ai_notes": None},
            {"id": "r2", "title": "Two", "started_at": None, "ended_at": None,
             "transcript": None, "ai_notes": None},
        ])
        result = runner.invoke(
            cli, ["recordings", "export", "--since", "7d", "--format", "md", "--to", "-"]
        )
    assert result.exit_code == 0
    assert "# One" in result.output and "# Two" in result.output
    assert "---" in result.output  # separator


def test_export_to_dir_writes_files(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    outdir = tmp_path / "out"
    runner = CliRunner()
    with patch("fellowai.commands.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([
            {"id": "r1", "title": "One", "started_at": None, "ended_at": None,
             "transcript": None, "ai_notes": None},
        ])
        result = runner.invoke(
            cli, ["recordings", "export", "--format", "both", "--to", str(outdir)]
        )
    assert result.exit_code == 0
    assert (outdir / "r1.json").exists()
    assert (outdir / "r1.md").exists()


def test_export_both_to_stdout_rejected(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli, ["recordings", "export", "--format", "both", "--to", "-"]
    )
    assert result.exit_code == 1
    assert "both" in result.output.lower()
