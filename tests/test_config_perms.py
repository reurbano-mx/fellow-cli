"""Verify save_config never leaves an API key with permissive permissions."""

import os
import stat

from fellowai.config import Config, ConfigError, save_config


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


def test_save_config_tightens_world_writable_parent_dir(tmp_path, monkeypatch):
    """A pre-existing permissive config dir must be tightened to 0o700."""
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    if os.name != "posix":
        return

    # Simulate a previously-created dir with permissive bits.
    os.chmod(tmp_path, 0o777)

    save_config(Config(subdomain="test", api_key="secretkey"))

    mode = stat.S_IMODE(tmp_path.stat().st_mode)
    assert mode & 0o077 == 0, f"parent dir still has group/world bits: {oct(mode)}"
    # Owner bits preserved
    assert mode & 0o700 == 0o700


def test_save_config_creates_private_dir_under_permissive_umask(tmp_path, monkeypatch):
    """Under umask 000, a fresh config dir must end up without group/world bits."""
    nested = tmp_path / "fresh"
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(nested))
    if os.name != "posix":
        return

    old_umask = os.umask(0o000)
    try:
        save_config(Config(subdomain="test", api_key="secretkey"))
    finally:
        os.umask(old_umask)

    mode = stat.S_IMODE(nested.stat().st_mode)
    assert mode & 0o077 == 0, f"dir is group/world accessible: {oct(mode)}"


def test_save_config_rejects_dir_not_owned_by_user(tmp_path, monkeypatch):
    """If the config dir is owned by another user, fail loudly."""
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(tmp_path))
    if os.name != "posix":
        return

    import pytest
    from unittest.mock import patch as mock_patch

    # Fake the directory's uid as something other than os.getuid().
    real_stat = os.stat
    real_uid = os.getuid()

    class FakeStat:
        def __init__(self, st):
            self.st_uid = real_uid + 1  # not us
            self.st_mode = st.st_mode

    def fake_stat(path, *args, **kwargs):
        st = real_stat(path, *args, **kwargs)
        if str(path) == str(tmp_path):
            return FakeStat(st)
        return st

    with mock_patch("fellowai.config.os.stat", side_effect=fake_stat):
        with pytest.raises(ConfigError, match="not owned by the current user"):
            save_config(Config(subdomain="test", api_key="secretkey"))


def test_save_config_hardens_every_created_intermediate_dir(tmp_path, monkeypatch):
    """Under umask 000, every intermediate dir created by save_config
    must end up without group/world bits — not just the leaf."""
    if os.name != "posix":
        return

    nested = tmp_path / "a" / "b" / "c"
    monkeypatch.setenv("FELLOWAI_CONFIG_DIR", str(nested))

    old_umask = os.umask(0o000)
    try:
        save_config(Config(subdomain="test", api_key="secretkey"))
    finally:
        os.umask(old_umask)

    for d in [tmp_path / "a", tmp_path / "a" / "b", nested]:
        mode = stat.S_IMODE(d.stat().st_mode)
        assert mode & 0o077 == 0, (
            f"intermediate {d} has group/world bits: {oct(mode)}"
        )
        assert mode & 0o700 == 0o700
