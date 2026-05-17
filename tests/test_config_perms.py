"""Verify save_config never leaves an API key with permissive permissions."""

import os
import stat

from fellowai.config import Config, save_config


def test_save_config_writes_with_0600_atomically(tmp_path, monkeypatch):
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    # Permissive umask to exercise the race window: if save_config used
    # plain open() + chmod(), the file would briefly exist as 0o644.
    old_umask = os.umask(0o022)
    try:
        save_config(Config(subdomain="test", api_key="secretkey"))
    finally:
        os.umask(old_umask)

    if os.name != "posix":
        return  # chmod semantics don't apply on Windows
    path = tmp_path / "config.toml"
    assert path.exists()
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"
    # No leftover .tmp sibling
    assert not (tmp_path / "config.toml.tmp").exists()
