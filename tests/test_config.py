import os
from pathlib import Path

import pytest

from fellowai.config import Config, ConfigError, load_config, save_config


def test_save_and_load_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    cfg = Config(subdomain="reurbano", api_key="secret-123")
    save_config(cfg)
    loaded = load_config()
    assert loaded.subdomain == "reurbano"
    assert loaded.api_key == "secret-123"


def test_load_env_var_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FELLOWAI_SUBDOMAIN", "envspace")
    monkeypatch.setenv("FELLOWAI_API_KEY", "env-key")
    loaded = load_config()
    assert loaded.subdomain == "envspace"
    assert loaded.api_key == "env-key"


def test_load_missing_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("FELLOWAI_SUBDOMAIN", raising=False)
    monkeypatch.delenv("FELLOWAI_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="No Fellow workspace configured"):
        load_config()


def test_save_creates_file_with_mode_600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    save_config(Config(subdomain="x", api_key="y"))
    path = tmp_path / "config.toml"
    assert path.exists()
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_delete_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fellowai.config import delete_config
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    save_config(Config(subdomain="a", api_key="b"))
    delete_config()
    assert not (tmp_path / "config.toml").exists()
