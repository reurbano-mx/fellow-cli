from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from fellowai.cli import cli


def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FELLOWAI_SUBDOMAIN", "test")
    monkeypatch.setenv("FELLOWAI_API_KEY", "k")


def test_error_without_debug_is_sentence(tmp_path, monkeypatch):
    from fellowai.client import AuthError
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.side_effect = AuthError("Unauthorized")
        result = runner.invoke(cli, ["recordings", "list"])
    assert result.exit_code == 2
    assert "Traceback" not in result.output
    assert "Unauthorized" in result.output


def test_error_with_debug_shows_traceback(tmp_path, monkeypatch):
    from fellowai.client import AuthError
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.side_effect = AuthError("Unauthorized")
        result = runner.invoke(cli, ["--debug", "recordings", "list"])
    assert result.exit_code != 0
    assert "Traceback" in result.output or "AuthError" in result.output
