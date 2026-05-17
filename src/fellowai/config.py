"""Config persistence: subdomain + API key in TOML under platform config dir."""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
import tomli_w


class ConfigError(Exception):
    """Raised for missing or invalid configuration."""


@dataclass
class Config:
    subdomain: str
    api_key: str


def _config_dir() -> Path:
    override = os.environ.get("FELLOWAI_CONFIG_DIR")
    if override:
        return Path(override)
    return Path(user_config_dir("fellowai", appauthor=False))


def _config_path() -> Path:
    return _config_dir() / "config.toml"


def _verify_dir(d: Path) -> None:
    """Refuse anything that isn't a real, user-owned directory."""
    st = d.lstat()
    if not stat.S_ISDIR(st.st_mode):
        raise ConfigError(
            f"Refusing to write config: {d} is not a directory."
        )
    if st.st_uid != os.getuid():
        raise ConfigError(
            f"Refusing to write config: {d} is not owned by the current user."
        )


def _prepare_config_dir(parent: Path) -> None:
    """Create the config dir tree as 0o700 on POSIX; reject unsafe components.

    Without this, mkdir(parents=True) honors the process umask, so under a
    permissive umask any newly-created ancestor — not just the leaf —
    could end up world-writable. A local attacker with write access to an
    intermediate dir could rename or replace the leaf between the chmod
    here and the os.replace in save_config.
    """
    if os.name != "posix":
        parent.mkdir(parents=True, exist_ok=True)
        return

    # Identify missing ancestors so we can create + harden each one.
    missing: list[Path] = []
    cur = parent
    while not cur.exists():
        missing.append(cur)
        cur = cur.parent

    # Create top-down. mode=0o700 is umask-ANDed (so it can land permissive
    # under umask 000); follow up with explicit chmod and lstat-verify.
    for d in reversed(missing):
        d.mkdir(mode=0o700, exist_ok=False)
        os.chmod(d, 0o700)
        _verify_dir(d)

    # Re-validate the leaf and tighten group/world bits if a pre-existing
    # dir was permissive.
    _verify_dir(parent)
    mode = stat.S_IMODE(parent.lstat().st_mode)
    if mode & 0o077:
        os.chmod(parent, mode & 0o700)


def save_config(cfg: Config) -> None:
    path = _config_path()
    _prepare_config_dir(path.parent)
    data = {"subdomain": cfg.subdomain, "api_key": cfg.api_key}

    if os.name == "posix":
        # tempfile.mkstemp opens with O_CREAT|O_EXCL and a randomized name,
        # so we never reuse a stale file (whose mode would be preserved by
        # O_TRUNC) and never follow a planted symlink. fchmod on the fresh
        # fd nails the mode to 0o600 regardless of umask before any bytes
        # are written. Atomic replace then moves it into position.
        import tempfile
        fd, tmp_name = tempfile.mkstemp(
            prefix=".config-", suffix=".toml", dir=str(path.parent)
        )
        tmp_path = Path(tmp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as f:
                tomli_w.dump(data, f)
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise
    else:
        with path.open("wb") as f:
            tomli_w.dump(data, f)


def load_config() -> Config:
    env_sub = os.environ.get("FELLOWAI_SUBDOMAIN")
    env_key = os.environ.get("FELLOWAI_API_KEY")
    if env_sub and env_key:
        return Config(subdomain=env_sub, api_key=env_key)

    path = _config_path()
    if not path.exists():
        raise ConfigError(
            "No Fellow workspace configured. Run 'fellowai login' to set one up."
        )
    with path.open("rb") as f:
        data = tomllib.load(f)
    try:
        return Config(subdomain=data["subdomain"], api_key=data["api_key"])
    except KeyError as e:
        raise ConfigError(f"Config file at {path} is missing key: {e}") from e


def delete_config() -> None:
    path = _config_path()
    if path.exists():
        path.unlink()
