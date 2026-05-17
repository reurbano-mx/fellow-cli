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


def _verify_dir_fd(fd: int, path_for_errors: Path) -> None:
    """Refuse anything that isn't a real, user-owned directory (fd-based)."""
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode):
        raise ConfigError(
            f"Refusing to write config: {path_for_errors} is not a directory."
        )
    if st.st_uid != os.getuid():
        raise ConfigError(
            f"Refusing to write config: {path_for_errors} is not owned by the current user."
        )


def _prepare_config_dir(parent: Path) -> None:
    """Create the config dir tree as 0o700 on POSIX; reject unsafe components.

    Race-free version: every dir is opened with O_DIRECTORY|O_NOFOLLOW so a
    symlink swap between mkdir and chmod can never trick us into chmod'ing
    an attacker-chosen target. Ownership and mode are verified via
    fstat/fchmod on the open fd, never via pathname after a lookup.
    """
    if os.name != "posix":
        parent.mkdir(parents=True, exist_ok=True)
        return

    # Identify missing components (top-down) and the lowest existing base.
    components: list[str] = []
    cur = parent
    while not cur.exists():
        components.append(cur.name)
        cur = cur.parent
    components.reverse()
    base = cur

    # Open the base directory without following symlinks at the leaf.
    fds: list[int] = []
    try:
        fds.append(os.open(base, os.O_DIRECTORY | os.O_NOFOLLOW))

        # Walk down, creating + verifying + fchmod'ing each missing component.
        rebuilt = base
        for name in components:
            rebuilt = rebuilt / name
            os.mkdir(name, mode=0o700, dir_fd=fds[-1])
            new_fd = os.open(
                name, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fds[-1]
            )
            fds.append(new_fd)
            _verify_dir_fd(new_fd, rebuilt)
            os.fchmod(new_fd, 0o700)

        # The leaf fd is fds[-1]. If parent already existed (no components
        # added), fds[-1] is the base/leaf. Verify and tighten its mode.
        leaf_fd = fds[-1]
        _verify_dir_fd(leaf_fd, parent)
        mode = stat.S_IMODE(os.fstat(leaf_fd).st_mode)
        if mode & 0o077:
            os.fchmod(leaf_fd, mode & 0o700)
    finally:
        for fd in fds:
            try:
                os.close(fd)
            except OSError:
                pass


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
