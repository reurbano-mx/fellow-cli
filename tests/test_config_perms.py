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


def test_save_config_ignores_planted_permissive_tmp(tmp_path, monkeypatch):
    """A stale or planted config.toml.tmp must not influence the final perms."""
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    if os.name != "posix":
        return

    # Pre-plant a sibling at the old predictable name with permissive mode.
    stale = tmp_path / "config.toml.tmp"
    stale.write_bytes(b"old garbage")
    os.chmod(stale, 0o644)

    old_umask = os.umask(0o022)
    try:
        save_config(Config(subdomain="test", api_key="secretkey"))
    finally:
        os.umask(old_umask)

    final = tmp_path / "config.toml"
    assert final.exists()
    mode = stat.S_IMODE(final.stat().st_mode)
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"
    # The planted stale file must remain untouched (mkstemp uses a fresh name)
    assert stale.exists()
    assert stale.read_bytes() == b"old garbage"


def test_save_config_does_not_follow_symlink_planted_at_tmp(tmp_path, monkeypatch):
    """A symlink at the predictable temp path must not redirect the write."""
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    if os.name != "posix":
        return

    victim = tmp_path / "victim"
    victim.write_bytes(b"untouched")
    os.chmod(victim, 0o644)

    # Plant a symlink at the legacy predictable temp path pointing at victim.
    link = tmp_path / "config.toml.tmp"
    os.symlink(victim, link)

    save_config(Config(subdomain="test", api_key="secretkey"))

    # Victim was not written through.
    assert victim.read_bytes() == b"untouched"
    assert stat.S_IMODE(victim.stat().st_mode) == 0o644

    # Final config exists at 0o600.
    final = tmp_path / "config.toml"
    assert final.exists()
    assert stat.S_IMODE(final.stat().st_mode) == 0o600
