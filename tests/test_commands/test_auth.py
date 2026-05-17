from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from fellowai.cli import cli


def test_login_validates_and_saves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    runner = CliRunner()
    with patch("fellowai.commands.auth.FellowClient") as MockClient:
        MockClient.return_value.get_me.return_value = {
            "user": {"email": "kramer@reurbano.mx", "full_name": "Kramer Sharp", "id": "u1"},
            "workspace": {"subdomain": "reurbano", "name": "Reurbano", "id": "w1"},
        }
        result = runner.invoke(cli, ["login"], input="reurbano\nsecretkey123\n")
    assert result.exit_code == 0, result.output
    assert "kramer@reurbano.mx" in result.output
    assert (tmp_path / "config.toml").exists()


def test_login_bad_key_fails_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fellowai.client import AuthError
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    runner = CliRunner()
    with patch("fellowai.commands.auth.FellowClient") as MockClient:
        MockClient.return_value.get_me.side_effect = AuthError("Unauthorized")
        result = runner.invoke(cli, ["login"], input="reurbano\nbadkey\n")
    assert result.exit_code == 2
    assert "isn't valid" in result.output or "Unauthorized" in result.output
    assert not (tmp_path / "config.toml").exists()


def test_me_prints_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FELLOWAI_SUBDOMAIN", "reurbano")
    monkeypatch.setenv("FELLOWAI_API_KEY", "k")
    runner = CliRunner()
    with patch("fellowai.commands.auth.FellowClient") as MockClient:
        MockClient.return_value.get_me.return_value = {
            "user": {"email": "x@y.com", "full_name": "X Y", "id": "u"},
            "workspace": {"subdomain": "reurbano", "name": "R", "id": "w"},
        }
        result = runner.invoke(cli, ["me"])
    assert result.exit_code == 0
    assert "x@y.com" in result.output
    assert "reurbano" in result.output


def test_me_without_config_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("FELLOWAI_SUBDOMAIN", raising=False)
    monkeypatch.delenv("FELLOWAI_API_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(cli, ["me"])
    assert result.exit_code == 2
    assert "No Fellow workspace configured" in result.output


def test_logout_deletes_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fellowai.config import Config, save_config
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    save_config(Config(subdomain="a", api_key="b"))
    runner = CliRunner()
    result = runner.invoke(cli, ["logout"])
    assert result.exit_code == 0
    assert not (tmp_path / "config.toml").exists()
