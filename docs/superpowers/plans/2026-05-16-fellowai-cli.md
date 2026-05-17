# fellowai CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform Python CLI (`fellowai`) that wraps Fellow.ai's REST API for recordings, notes, and action items — with pipeable JSON output, an interactive action-item picker, write operations, and zero permanent context cost in Claude Code sessions.

**Architecture:** Click app over an httpx-based client. Single `FellowClient` owns auth/pagination/retry/error-mapping. Single `output` module owns TTY-vs-pipe rendering. Commands per resource (`recordings`, `notes`, `action-items`) compose those two. Configuration via `platformdirs`-located TOML with env-var override.

**Tech Stack:** Python 3.10+, Click 8, httpx, Pydantic v2, rich, questionary, platformdirs, pytest, respx, vcrpy. Pure-Python (no native build).

**Reference spec:** `docs/superpowers/specs/2026-05-16-fellow-cli-design.md`

---

## Phase 1 — Foundation

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/fellowai/__init__.py`
- Create: `src/fellowai/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `.gitignore` (already exists with `.playwright-mcp/` and `.api-probe/` — append more)

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_smoke.py`:
```python
from click.testing import CliRunner

from fellowai.cli import cli


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "fellowai" in result.output


def test_help_lists_top_level_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in ["login", "logout", "me", "recordings", "notes", "action-items"]:
        assert cmd in result.output
```

- [ ] **Step 2: Run test, expect import failure**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fellowai'`

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "fellowai"
version = "0.1.0"
description = "Unofficial CLI for Fellow.ai's developer API"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Kramer Sharp", email = "kramer@reurbano.mx" }]
dependencies = [
    "click>=8.1",
    "httpx>=0.27",
    "pydantic>=2.6",
    "rich>=13.7",
    "questionary>=2.0",
    "platformdirs>=4.2",
    "tomli>=2.0; python_version < '3.11'",
    "tomli-w>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "respx>=0.20",
    "vcrpy>=6.0",
    "ruff>=0.4",
]

[project.scripts]
fellowai = "fellowai.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/fellowai"]

[tool.ruff]
line-length = 100
target-version = "py310"
```

- [ ] **Step 4: Create `src/fellowai/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Create `src/fellowai/__main__.py`**

```python
from fellowai.cli import cli

if __name__ == "__main__":
    cli()
```

- [ ] **Step 6: Create minimal `src/fellowai/cli.py`**

```python
import click

from fellowai import __version__


@click.group()
@click.version_option(__version__, prog_name="fellowai")
def cli() -> None:
    """Unofficial CLI for Fellow.ai's developer API."""


@cli.command()
def login() -> None:
    """Configure workspace and API key."""
    raise NotImplementedError


@cli.command()
def logout() -> None:
    """Delete stored configuration."""
    raise NotImplementedError


@cli.command()
def me() -> None:
    """Show authenticated identity and workspace."""
    raise NotImplementedError


@cli.group()
def recordings() -> None:
    """Recording operations."""


@cli.group()
def notes() -> None:
    """Note operations."""


@cli.group(name="action-items")
def action_items() -> None:
    """Action item operations."""
```

- [ ] **Step 7: Install package in editable mode and run tests**

Run: `pip install -e ".[dev]" && pytest tests/test_smoke.py -v`
Expected: 2 passed

- [ ] **Step 8: Append to `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
.ruff_cache/
dist/
build/
*.egg-info/
.venv/
venv/
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml src/ tests/ .gitignore
git commit -m "feat: scaffold fellowai package with click skeleton and smoke test"
```

---

### Task 2: `time_parse` — relative + absolute date parser

**Files:**
- Create: `src/fellowai/time_parse.py`
- Create: `tests/test_time_parse.py`

This module turns `--since 7d`, `--since 2w`, `--since 2026-04-01` into an ISO-8601 string the API filters accept.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_time_parse.py`:
```python
from datetime import datetime, timezone

import pytest

from fellowai.time_parse import parse_since


def test_parse_relative_days():
    now = datetime(2026, 5, 16, tzinfo=timezone.utc)
    assert parse_since("7d", now=now) == "2026-05-09T00:00:00Z"


def test_parse_relative_weeks():
    now = datetime(2026, 5, 16, tzinfo=timezone.utc)
    assert parse_since("2w", now=now) == "2026-05-02T00:00:00Z"


def test_parse_relative_hours():
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    assert parse_since("3h", now=now) == "2026-05-16T09:00:00Z"


def test_parse_absolute_date():
    assert parse_since("2026-04-01") == "2026-04-01T00:00:00Z"


def test_parse_absolute_datetime():
    assert parse_since("2026-04-01T15:30:00Z") == "2026-04-01T15:30:00Z"


def test_invalid_format_raises():
    with pytest.raises(ValueError, match="Unrecognized date"):
        parse_since("not-a-date")


def test_unknown_unit_raises():
    with pytest.raises(ValueError, match="Unrecognized date"):
        parse_since("7x")
```

- [ ] **Step 2: Run tests, expect import failure**

Run: `pytest tests/test_time_parse.py -v`
Expected: FAIL on import

- [ ] **Step 3: Implement `time_parse.py`**

```python
"""Parse user-supplied --since/--until values into ISO-8601 UTC strings."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_RELATIVE = re.compile(r"^(\d+)([hdw])$")
_UNIT_TO_TIMEDELTA = {
    "h": lambda n: timedelta(hours=n),
    "d": lambda n: timedelta(days=n),
    "w": lambda n: timedelta(weeks=n),
}


def parse_since(value: str, *, now: datetime | None = None) -> str:
    """Convert a user-supplied date into an ISO-8601 UTC string."""
    now = now or datetime.now(timezone.utc)

    m = _RELATIVE.match(value)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        dt = now - _UNIT_TO_TIMEDELTA[unit](n)
        if unit in ("d", "w"):
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            dt = dt.replace(minute=0, second=0, microsecond=0)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

    raise ValueError(f"Unrecognized date: {value!r}. Use e.g. '7d', '2w', '2026-04-01'.")
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_time_parse.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/fellowai/time_parse.py tests/test_time_parse.py
git commit -m "feat(time_parse): parse relative and absolute --since values to ISO-8601"
```

---

### Task 3: `config` — TOML persistence + env override

**Files:**
- Create: `src/fellowai/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run tests, expect import failure**

Run: `pytest tests/test_config.py -v`
Expected: FAIL on import

- [ ] **Step 3: Implement `config.py`**

```python
"""Config persistence: subdomain + API key in TOML under platform config dir."""

from __future__ import annotations

import os
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


def save_config(cfg: Config) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        tomli_w.dump({"subdomain": cfg.subdomain, "api_key": cfg.api_key}, f)
    if os.name == "posix":
        path.chmod(0o600)


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
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_config.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/fellowai/config.py tests/test_config.py
git commit -m "feat(config): TOML config with env var override and 600 perms"
```

---

## Phase 2 — API Client

### Task 4: `client` foundation — auth, `/me`, error mapping

**Files:**
- Create: `src/fellowai/client.py`
- Create: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client.py`:
```python
import pytest
import respx
from httpx import Response

from fellowai.client import (
    AuthError,
    BadRequestError,
    FellowClient,
    NotFoundError,
    RateLimitError,
    ServerError,
)


def _client() -> FellowClient:
    return FellowClient(subdomain="test", api_key="key-abc")


@respx.mock
def test_get_me_success():
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(200, json={
            "user": {"id": "u1", "email": "x@y.com", "full_name": "X Y"},
            "workspace": {"id": "w1", "name": "wsname", "subdomain": "test"},
        })
    )
    me = _client().get_me()
    assert me["user"]["email"] == "x@y.com"
    assert me["workspace"]["subdomain"] == "test"


@respx.mock
def test_auth_header_sent():
    route = respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(200, json={"user": {}, "workspace": {}})
    )
    _client().get_me()
    assert route.calls[0].request.headers["X-API-KEY"] == "key-abc"


@respx.mock
def test_401_raises_auth_error():
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(401, json={"detail": "Unauthorized"})
    )
    with pytest.raises(AuthError, match="Unauthorized"):
        _client().get_me()


@respx.mock
def test_404_raises_not_found():
    respx.get("https://test.fellow.app/api/v1/recording/x").mock(
        return_value=Response(404, json={"detail": "Recording not found"})
    )
    with pytest.raises(NotFoundError, match="Recording not found"):
        _client().get_recording("x")


@respx.mock
def test_400_simple_detail_raises_bad_request():
    respx.get("https://test.fellow.app/api/v1/recording/x").mock(
        return_value=Response(400, json={"detail": "Invalid recording ID format"})
    )
    with pytest.raises(BadRequestError, match="Invalid recording ID format"):
        _client().get_recording("x")


@respx.mock
def test_400_structured_validation_raises_bad_request_with_locations():
    respx.post("https://test.fellow.app/api/v1/recordings").mock(
        return_value=Response(400, json={
            "message": "Request could not be completed due to validation errors.",
            "errors": [{"location": "page_size", "message": "Input should be less than or equal to 50"}],
        })
    )
    with pytest.raises(BadRequestError) as exc:
        list(_client().list_recordings(page_size=9999))
    assert "page_size" in str(exc.value)
    assert "less than or equal to 50" in str(exc.value)


@respx.mock
def test_429_raises_rate_limit_error():
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(429, json={"detail": "rate_limited"})
    )
    with pytest.raises(RateLimitError):
        _client().get_me()


@respx.mock
def test_500_raises_server_error():
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(500, text="Internal Server Error")
    )
    with pytest.raises(ServerError):
        _client().get_me()


@respx.mock
def test_subdomain_returns_html_raises_auth_error():
    # Wrong-subdomain probe returned HTML at 200 — we treat as auth failure.
    respx.get("https://wrong.fellow.app/api/v1/me").mock(
        return_value=Response(200, html="<!doctype html><html>...</html>")
    )
    client = FellowClient(subdomain="wrong", api_key="x")
    with pytest.raises(AuthError, match="subdomain"):
        client.get_me()
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_client.py -v`
Expected: FAIL on import

- [ ] **Step 3: Implement minimal `client.py`**

```python
"""Single point of contact with Fellow's REST API."""

from __future__ import annotations

import json
from typing import Any, Iterator

import httpx


class FellowError(Exception):
    """Base for all client-mapped Fellow API errors."""


class AuthError(FellowError):
    """401 from API, or non-JSON response (likely wrong subdomain)."""


class NotFoundError(FellowError):
    """404 from API."""


class BadRequestError(FellowError):
    """400 from API."""


class RateLimitError(FellowError):
    """429 from API."""


class ServerError(FellowError):
    """5xx from API."""


class FellowClient:
    def __init__(self, *, subdomain: str, api_key: str, timeout: float = 30.0) -> None:
        self._subdomain = subdomain
        self._base = f"https://{subdomain}.fellow.app/api/v1"
        self._http = httpx.Client(
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    def _request(self, method: str, path: str, *, json_body: dict | None = None) -> Any:
        url = f"{self._base}{path}"
        resp = self._http.request(method, url, json=json_body)
        self._raise_for_status(resp)
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise AuthError(
                f"Got non-JSON response from {self._subdomain}.fellow.app — "
                "did you type the subdomain correctly?"
            ) from e

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            ct = resp.headers.get("content-type", "")
            if "json" not in ct and resp.text.strip().startswith("<"):
                raise AuthError(
                    f"Got HTML response from {self._subdomain}.fellow.app — "
                    "the subdomain is likely wrong."
                )
            return

        try:
            body = resp.json()
        except json.JSONDecodeError:
            body = {"detail": resp.text or f"HTTP {resp.status_code}"}

        message = self._format_error(body)

        if resp.status_code == 401:
            raise AuthError(message)
        if resp.status_code == 404:
            raise NotFoundError(message)
        if resp.status_code == 429:
            raise RateLimitError(message)
        if resp.status_code >= 500:
            raise ServerError(message)
        if resp.status_code >= 400:
            raise BadRequestError(message)

    @staticmethod
    def _format_error(body: dict) -> str:
        if "detail" in body:
            return str(body["detail"])
        if "errors" in body and isinstance(body["errors"], list):
            parts = [f"{e.get('location', '?')}: {e.get('message', '?')}" for e in body["errors"]]
            return body.get("message", "Validation error") + " — " + "; ".join(parts)
        return str(body)

    # ---- Resource methods (real impls in later tasks) ----

    def get_me(self) -> dict:
        return self._request("GET", "/me")

    def get_recording(self, recording_id: str) -> dict:
        return self._request("GET", f"/recording/{recording_id}")

    def list_recordings(self, *, page_size: int = 20) -> Iterator[dict]:
        # Full pagination + filters in Task 5/7. Stub for now.
        body = {"pagination": {"cursor": None, "page_size": page_size}}
        data = self._request("POST", "/recordings", json_body=body)
        yield from data["recordings"]["data"]
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_client.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/fellowai/client.py tests/test_client.py
git commit -m "feat(client): httpx-based FellowClient with typed error mapping"
```

---

### Task 5: Cursor pagination iterator

**Files:**
- Modify: `src/fellowai/client.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_client.py`:
```python
@respx.mock
def test_pagination_walks_cursors_until_null():
    # Page 1: returns cursor "p2", 2 items
    # Page 2: returns cursor null, 1 item
    route = respx.post("https://test.fellow.app/api/v1/recordings")
    route.mock(side_effect=[
        Response(200, json={
            "recordings": {
                "page_info": {"cursor": "p2", "page_size": 2},
                "data": [{"id": "r1"}, {"id": "r2"}],
            }
        }),
        Response(200, json={
            "recordings": {
                "page_info": {"cursor": None, "page_size": 2},
                "data": [{"id": "r3"}],
            }
        }),
    ])
    items = list(_client().list_recordings(page_size=2))
    assert [i["id"] for i in items] == ["r1", "r2", "r3"]
    assert len(route.calls) == 2
    assert route.calls[1].request.read() == b'{"pagination": {"cursor": "p2", "page_size": 2}}'


@respx.mock
def test_pagination_honors_limit():
    route = respx.post("https://test.fellow.app/api/v1/recordings")
    route.mock(side_effect=[
        Response(200, json={
            "recordings": {
                "page_info": {"cursor": "p2", "page_size": 10},
                "data": [{"id": f"r{i}"} for i in range(10)],
            }
        }),
    ])
    items = list(_client().list_recordings(limit=3, page_size=10))
    assert len(items) == 3
    assert len(route.calls) == 1  # didn't fetch the second page


def test_client_validates_page_size_bounds():
    with pytest.raises(ValueError, match="page_size"):
        list(_client().list_recordings(page_size=51))
    with pytest.raises(ValueError, match="page_size"):
        list(_client().list_recordings(page_size=0))
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_client.py::test_pagination_walks_cursors_until_null tests/test_client.py::test_pagination_honors_limit tests/test_client.py::test_client_validates_page_size_bounds -v`
Expected: FAIL

- [ ] **Step 3: Replace `list_recordings` and add a shared paginator**

In `src/fellowai/client.py`, replace the stub `list_recordings` with:

```python
    def list_recordings(
        self,
        *,
        filters: dict | None = None,
        include: dict | None = None,
        media_url: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        page_size: int = 20,
    ) -> Iterator[dict]:
        return self._paginate(
            "/recordings",
            response_key="recordings",
            filters=filters,
            include=include,
            extra_body={"media_url": media_url} if media_url else None,
            order_by=order_by,
            limit=limit,
            page_size=page_size,
        )

    def _paginate(
        self,
        path: str,
        *,
        response_key: str,
        filters: dict | None,
        include: dict | None,
        extra_body: dict | None = None,
        order_by: str | None = None,
        limit: int | None,
        page_size: int,
    ) -> Iterator[dict]:
        if not 1 <= page_size <= 50:
            raise ValueError("page_size must be between 1 and 50")

        cursor: str | None = None
        yielded = 0
        while True:
            body: dict = {"pagination": {"cursor": cursor, "page_size": page_size}}
            if filters:
                body["filters"] = filters
            if include:
                body["include"] = include
            if order_by:
                body["order_by"] = order_by
            if extra_body:
                body.update(extra_body)

            data = self._request("POST", path, json_body=body)
            page = data[response_key]
            for item in page["data"]:
                if limit is not None and yielded >= limit:
                    return
                yield item
                yielded += 1
            cursor = page["page_info"]["cursor"]
            if cursor is None:
                return
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_client.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add src/fellowai/client.py tests/test_client.py
git commit -m "feat(client): cursor-paginated iterator with limit and page_size validation"
```

---

### Task 6: Retry on 429 / 5xx with backoff

**Files:**
- Modify: `src/fellowai/client.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_client.py`:
```python
@respx.mock
def test_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []
    monkeypatch.setattr("fellowai.client.time.sleep", lambda s: sleeps.append(s))
    respx.get("https://test.fellow.app/api/v1/me").mock(side_effect=[
        Response(429, json={"detail": "rate_limited"}, headers={"Retry-After": "1"}),
        Response(200, json={"user": {}, "workspace": {}}),
    ])
    _client().get_me()
    assert sleeps == [1.0]


@respx.mock
def test_retries_on_500_with_exponential_backoff(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []
    monkeypatch.setattr("fellowai.client.time.sleep", lambda s: sleeps.append(s))
    respx.get("https://test.fellow.app/api/v1/me").mock(side_effect=[
        Response(500, text="bad"),
        Response(500, text="bad"),
        Response(200, json={"user": {}, "workspace": {}}),
    ])
    _client().get_me()
    assert sleeps == [1.0, 2.0]


@respx.mock
def test_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fellowai.client.time.sleep", lambda s: None)
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(500, text="bad"),
    )
    with pytest.raises(ServerError):
        _client().get_me()
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_client.py::test_retries_on_429_then_succeeds tests/test_client.py::test_retries_on_500_with_exponential_backoff tests/test_client.py::test_gives_up_after_max_retries -v`
Expected: FAIL

- [ ] **Step 3: Add retry logic in `client.py`**

At the top of `src/fellowai/client.py`, add `import time`. Replace `_request` with:

```python
    _MAX_RETRIES = 3

    def _request(self, method: str, path: str, *, json_body: dict | None = None) -> Any:
        url = f"{self._base}{path}"
        attempt = 0
        while True:
            resp = self._http.request(method, url, json=json_body)
            if resp.status_code == 429 and attempt < self._MAX_RETRIES:
                wait = float(resp.headers.get("Retry-After", 2**attempt))
                time.sleep(wait)
                attempt += 1
                continue
            if 500 <= resp.status_code < 600 and attempt < self._MAX_RETRIES:
                time.sleep(2**attempt)
                attempt += 1
                continue
            break

        self._raise_for_status(resp)
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise AuthError(
                f"Got non-JSON response from {self._subdomain}.fellow.app — "
                "did you type the subdomain correctly?"
            ) from e
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_client.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add src/fellowai/client.py tests/test_client.py
git commit -m "feat(client): retry 429 with Retry-After and 5xx with exponential backoff"
```

---

### Task 7: Resource methods — notes, action items, single-resource gets, writes

**Files:**
- Modify: `src/fellowai/client.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_client.py`:
```python
# Filter/include whitelists

ALLOWED_RECORDING_FILTERS = {
    "event_guid", "created_at_start", "created_at_end",
    "updated_at_start", "updated_at_end", "channel_id", "title",
}
ALLOWED_RECORDING_INCLUDES = {"transcript", "ai_notes", "media_url"}
ALLOWED_ACTION_ITEM_FILTERS = {
    "scope", "completed", "archived", "ai_detected", "ai_suggestion_accepted_by_user",
}


def test_rejects_unknown_recording_filter():
    with pytest.raises(ValueError, match="Unknown filter"):
        list(_client().list_recordings(filters={"titel": "x"}))


def test_rejects_unknown_recording_include():
    with pytest.raises(ValueError, match="Unknown include"):
        list(_client().list_recordings(include={"transcrip": True}))


def test_rejects_unknown_action_item_filter():
    with pytest.raises(ValueError, match="Unknown filter"):
        list(_client().list_action_items(filters={"compleeted": True}))


@respx.mock
def test_list_notes():
    respx.post("https://test.fellow.app/api/v1/notes").mock(
        return_value=Response(200, json={
            "notes": {
                "page_info": {"cursor": None, "page_size": 20},
                "data": [{"id": "n1", "title": "T"}],
            }
        }),
    )
    items = list(_client().list_notes())
    assert items == [{"id": "n1", "title": "T"}]


@respx.mock
def test_get_note():
    respx.get("https://test.fellow.app/api/v1/note/abc").mock(
        return_value=Response(200, json={"note": {"id": "abc"}})
    )
    note = _client().get_note("abc")
    assert note["id"] == "abc"


@respx.mock
def test_list_action_items_sends_filters_and_order():
    route = respx.post("https://test.fellow.app/api/v1/action_items").mock(
        return_value=Response(200, json={
            "action_items": {
                "page_info": {"cursor": None, "page_size": 20},
                "data": [],
            }
        }),
    )
    list(_client().list_action_items(
        filters={"scope": "assigned_to_me", "completed": False},
        order_by="due_date",
    ))
    sent = json.loads(route.calls[0].request.read())
    assert sent["filters"] == {"scope": "assigned_to_me", "completed": False}
    assert sent["order_by"] == "due_date"


@respx.mock
def test_get_action_item():
    respx.get("https://test.fellow.app/api/v1/action_item/x").mock(
        return_value=Response(200, json={"action_item": {"id": "x", "status": "Incomplete"}})
    )
    item = _client().get_action_item("x")
    assert item["status"] == "Incomplete"


@respx.mock
def test_set_action_item_completed_true():
    route = respx.post("https://test.fellow.app/api/v1/action_item/x/complete").mock(
        return_value=Response(200, json={"action_item": {"id": "x", "status": "Done"}})
    )
    result = _client().set_action_item_completed("x", True)
    assert result["status"] == "Done"
    assert json.loads(route.calls[0].request.read()) == {"completed": True}


@respx.mock
def test_set_action_item_completed_false():
    route = respx.post("https://test.fellow.app/api/v1/action_item/x/complete").mock(
        return_value=Response(200, json={"action_item": {"id": "x", "status": "Incomplete"}})
    )
    _client().set_action_item_completed("x", False)
    assert json.loads(route.calls[0].request.read()) == {"completed": False}


@respx.mock
def test_archive_action_item():
    route = respx.post("https://test.fellow.app/api/v1/action_item/x/archive").mock(
        return_value=Response(200, json={"action_item": {"id": "x", "status": "Archived"}})
    )
    result = _client().archive_action_item("x")
    assert result["status"] == "Archived"
    assert json.loads(route.calls[0].request.read()) == {}


def test_rejects_unknown_action_item_order():
    with pytest.raises(ValueError, match="order_by"):
        list(_client().list_action_items(order_by="alphabetical"))
```

Also add `import json` at the top of the test file if not already present.

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_client.py -v`
Expected: FAIL on new tests

- [ ] **Step 3: Extend `client.py` with whitelists + the new methods**

Add the constants near the top of `src/fellowai/client.py`, after the exception classes:

```python
ALLOWED_RECORDING_FILTERS: frozenset[str] = frozenset({
    "event_guid", "created_at_start", "created_at_end",
    "updated_at_start", "updated_at_end", "channel_id", "title",
})
ALLOWED_RECORDING_INCLUDES: frozenset[str] = frozenset({
    "transcript", "ai_notes", "media_url",
})
ALLOWED_NOTE_FILTERS: frozenset[str] = frozenset({"created_at_start", "created_at_end"})
ALLOWED_NOTE_INCLUDES: frozenset[str] = frozenset({"content_markdown", "event_attendees"})
ALLOWED_ACTION_ITEM_FILTERS: frozenset[str] = frozenset({
    "scope", "completed", "archived", "ai_detected", "ai_suggestion_accepted_by_user",
})
ALLOWED_ACTION_ITEM_ORDER_BY: frozenset[str] = frozenset({
    "created_at_desc", "created_at_asc", "due_date",
})


def _validate_keys(value: dict | None, allowed: frozenset[str], kind: str) -> None:
    if not value:
        return
    bad = set(value.keys()) - allowed
    if bad:
        raise ValueError(f"Unknown {kind}: {sorted(bad)}. Allowed: {sorted(allowed)}.")
```

Add a `_validate_keys` call inside `list_recordings`:

```python
        _validate_keys(filters, ALLOWED_RECORDING_FILTERS, "filter")
        _validate_keys(include, ALLOWED_RECORDING_INCLUDES, "include")
```

(put these lines at the top of the method body)

Add the new methods at the bottom of `FellowClient`:

```python
    def list_notes(
        self,
        *,
        filters: dict | None = None,
        include: dict | None = None,
        limit: int | None = None,
        page_size: int = 20,
    ) -> Iterator[dict]:
        _validate_keys(filters, ALLOWED_NOTE_FILTERS, "filter")
        _validate_keys(include, ALLOWED_NOTE_INCLUDES, "include")
        return self._paginate(
            "/notes",
            response_key="notes",
            filters=filters,
            include=include,
            limit=limit,
            page_size=page_size,
        )

    def get_note(self, note_id: str) -> dict:
        return self._request("GET", f"/note/{note_id}")["note"]

    def list_action_items(
        self,
        *,
        filters: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        page_size: int = 20,
    ) -> Iterator[dict]:
        _validate_keys(filters, ALLOWED_ACTION_ITEM_FILTERS, "filter")
        if order_by is not None and order_by not in ALLOWED_ACTION_ITEM_ORDER_BY:
            raise ValueError(
                f"Unknown order_by: {order_by!r}. Allowed: {sorted(ALLOWED_ACTION_ITEM_ORDER_BY)}."
            )
        return self._paginate(
            "/action_items",
            response_key="action_items",
            filters=filters,
            include=None,
            order_by=order_by,
            limit=limit,
            page_size=page_size,
        )

    def get_action_item(self, action_item_id: str) -> dict:
        return self._request("GET", f"/action_item/{action_item_id}")["action_item"]

    def set_action_item_completed(self, action_item_id: str, completed: bool) -> dict:
        return self._request(
            "POST",
            f"/action_item/{action_item_id}/complete",
            json_body={"completed": completed},
        )["action_item"]

    def archive_action_item(self, action_item_id: str) -> dict:
        return self._request("POST", f"/action_item/{action_item_id}/archive", json_body={})["action_item"]
```

Also: update existing `get_recording` to return the unwrapped recording:

```python
    def get_recording(self, recording_id: str) -> dict:
        return self._request("GET", f"/recording/{recording_id}")["recording"]
```

Update the existing `test_get_recording` if any other test expects the wrapper.

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_client.py -v`
Expected: 25+ passed

- [ ] **Step 5: Commit**

```bash
git add src/fellowai/client.py tests/test_client.py
git commit -m "feat(client): notes, action items, single-resource gets, writes, whitelist validation"
```

---

## Phase 3 — Output

### Task 8: `output` module — TTY detection, JSON/table/markdown renderers

**Files:**
- Create: `src/fellowai/output.py`
- Create: `tests/test_output.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_output.py`:
```python
import json
import sys
from io import StringIO

import pytest

from fellowai.output import emit, render_action_item_card, render_recording_markdown


def _capture(monkeypatch: pytest.MonkeyPatch, isatty: bool) -> StringIO:
    buf = StringIO()
    buf.isatty = lambda: isatty  # type: ignore[method-assign]
    monkeypatch.setattr(sys, "stdout", buf)
    return buf


def test_list_piped_emits_json(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=False)
    emit([{"id": "a"}, {"id": "b"}], shape="list", columns=["id"])
    assert json.loads(buf.getvalue()) == [{"id": "a"}, {"id": "b"}]


def test_list_tty_emits_table(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=True)
    emit([{"id": "a", "name": "Alpha"}], shape="list", columns=["id", "name"])
    out = buf.getvalue()
    assert "id" in out and "name" in out and "Alpha" in out


def test_force_json_flag(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=True)
    emit([{"id": "a"}], shape="list", columns=["id"], format_override="json")
    assert json.loads(buf.getvalue()) == [{"id": "a"}]


def test_force_md_flag(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=False)
    rec = {"id": "x", "title": "T", "started_at": "2026-05-01T00:00:00Z", "ended_at": None,
           "transcript": None, "ai_notes": None}
    emit(rec, shape="document",
         markdown_renderer=lambda d: render_recording_markdown(d),
         format_override="md")
    out = buf.getvalue()
    assert "# T" in out


def test_empty_list_tty_friendly(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=True)
    emit([], shape="list", columns=["id"], empty_message="No recordings.")
    assert "No recordings." in buf.getvalue()


def test_empty_list_piped_emits_empty_array(monkeypatch: pytest.MonkeyPatch):
    buf = _capture(monkeypatch, isatty=False)
    emit([], shape="list", columns=["id"])
    assert json.loads(buf.getvalue()) == []


def test_render_recording_markdown_with_transcript():
    rec = {
        "id": "r1",
        "title": "Test Meeting",
        "started_at": "2026-05-01T10:00:00Z",
        "ended_at": "2026-05-01T10:30:00Z",
        "transcript": {
            "speech_segments": [
                {"start": 0.0, "end": 2.5, "speaker": "Alice", "text": "Hello."},
                {"start": 2.5, "end": 5.0, "speaker": "Bob", "text": "Hi back."},
            ],
            "language_code": "en",
        },
        "ai_notes": None,
    }
    md = render_recording_markdown(rec)
    assert "# Test Meeting" in md
    assert "[Alice]: Hello." in md
    assert "[Bob]: Hi back." in md


def test_render_recording_markdown_with_ai_notes():
    rec = {
        "id": "r1", "title": "T", "started_at": "2026-05-01T00:00:00Z", "ended_at": None,
        "transcript": None,
        "ai_notes": [{
            "id": "n1", "title": "AI Notes", "is_active": True, "template_creator": "fellow",
            "sections": [
                {"title": "Summary", "type": "STANDARD", "content": "We discussed plans."},
                {"title": "Decisions", "type": "STANDARD",
                 "content": [{"text": "Ship by Friday."}, {"text": "Hire one more."}]},
            ],
        }],
    }
    md = render_recording_markdown(rec)
    assert "## Summary" in md and "We discussed plans." in md
    assert "## Decisions" in md and "Ship by Friday." in md


def test_render_action_item_card():
    item = {
        "id": "x", "text": "Do thing",
        "status": "Incomplete",
        "due_date": "2026-06-01",
        "assignees": [{"full_name": "Alice", "email": "a@x.com"}],
        "ai_detected": True,
    }
    card = render_action_item_card(item)
    assert "Do thing" in card and "Incomplete" in card and "Alice" in card
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_output.py -v`
Expected: FAIL on import

- [ ] **Step 3: Implement `output.py`**

```python
"""TTY-aware rendering: JSON when piped, table/markdown when interactive."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Iterable, Literal

from rich.console import Console
from rich.table import Table

Shape = Literal["list", "document", "card"]
FormatOverride = Literal["json", "md", None]


def emit(
    data: Any,
    *,
    shape: Shape,
    columns: list[str] | None = None,
    markdown_renderer: Callable[[Any], str] | None = None,
    card_renderer: Callable[[Any], str] | None = None,
    format_override: FormatOverride = None,
    empty_message: str | None = None,
) -> None:
    """Render `data` to stdout based on shape, TTY state, and overrides."""
    is_tty = sys.stdout.isatty()

    if format_override == "json":
        _print_json(data)
        return
    if format_override == "md" and markdown_renderer is not None:
        sys.stdout.write(markdown_renderer(data))
        if not (markdown_renderer(data) or "").endswith("\n"):
            sys.stdout.write("\n")
        return

    if shape == "list":
        items: list = list(data) if not isinstance(data, list) else data
        if not items:
            if is_tty and empty_message:
                sys.stdout.write(empty_message + "\n")
            else:
                _print_json([])
            return
        if is_tty:
            _print_table(items, columns or [])
        else:
            _print_json(items)
        return

    if shape == "document":
        if markdown_renderer is not None:
            sys.stdout.write(markdown_renderer(data))
            if not (markdown_renderer(data) or "").endswith("\n"):
                sys.stdout.write("\n")
        else:
            _print_json(data)
        return

    if shape == "card":
        if is_tty and card_renderer is not None:
            sys.stdout.write(card_renderer(data) + "\n")
        else:
            _print_json(data)
        return

    raise ValueError(f"Unknown shape: {shape}")


def _print_json(data: Any) -> None:
    sys.stdout.write(json.dumps(data, separators=(",", ":"), default=str))
    sys.stdout.write("\n")


def _print_table(items: Iterable[dict], columns: list[str]) -> None:
    console = Console(file=sys.stdout, force_terminal=True)
    table = Table()
    for col in columns:
        table.add_column(col)
    for item in items:
        table.add_row(*[str(item.get(c, "") or "") for c in columns])
    console.print(table)


# ---- Resource-specific markdown / card renderers ----


def render_recording_markdown(rec: dict) -> str:
    lines = [f"# {rec.get('title') or rec['id']}", ""]
    started = rec.get("started_at")
    ended = rec.get("ended_at")
    if started:
        lines.append(f"**Started:** {started}")
    if ended:
        lines.append(f"**Ended:** {ended}")
    lines.append("")

    ai_notes = rec.get("ai_notes")
    if ai_notes:
        for note in ai_notes:
            for section in note.get("sections", []):
                lines.append(f"## {section.get('title', '')}")
                lines.append("")
                content = section.get("content")
                if isinstance(content, str):
                    lines.append(content)
                elif isinstance(content, list):
                    for entry in content:
                        if isinstance(entry, dict) and "text" in entry:
                            lines.append(f"- {entry['text']}")
                        else:
                            lines.append(f"- {entry}")
                lines.append("")

    transcript = rec.get("transcript")
    if transcript:
        lines.append("## Transcript")
        lines.append("")
        for seg in transcript.get("speech_segments", []):
            lines.append(f"[{seg['speaker']}]: {seg['text']}")
        lines.append("")

    return "\n".join(lines)


def render_note_markdown(note: dict) -> str:
    lines = [f"# {note.get('title') or note['id']}", ""]
    if note.get("event_start"):
        lines.append(f"**Event:** {note['event_start']} → {note.get('event_end', '?')}")
    attendees = note.get("event_attendees")
    if attendees:
        lines.append("**Attendees:** " + ", ".join(a.get("email", "?") for a in attendees))
    lines.append("")
    body = note.get("content_markdown")
    if body:
        lines.append(body)
    return "\n".join(lines)


def render_action_item_card(item: dict) -> str:
    lines = [
        f"**{item['text']}**",
        f"  Status: {item.get('status', '?')}",
    ]
    if item.get("due_date"):
        lines.append(f"  Due: {item['due_date']}")
    assignees = item.get("assignees") or []
    if assignees:
        lines.append("  Assignees: " + ", ".join(a.get("full_name", "?") for a in assignees))
    if item.get("ai_detected"):
        lines.append("  (AI-detected)")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_output.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/fellowai/output.py tests/test_output.py
git commit -m "feat(output): TTY-aware rendering with JSON/table/markdown renderers"
```

---

## Phase 4 — Commands

### Task 9: Auth commands — login, logout, me

**Files:**
- Create: `src/fellowai/commands/__init__.py` (empty)
- Create: `src/fellowai/commands/auth.py`
- Modify: `src/fellowai/cli.py` (wire up commands)
- Create: `tests/test_commands/__init__.py` (empty)
- Create: `tests/test_commands/test_auth.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_commands/test_auth.py`:
```python
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
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_commands/test_auth.py -v`
Expected: FAIL on import

- [ ] **Step 3: Implement `src/fellowai/commands/auth.py`**

```python
"""Login / logout / me commands."""

from __future__ import annotations

import sys
import webbrowser

import click

from fellowai.client import AuthError, FellowClient, FellowError
from fellowai.config import Config, ConfigError, delete_config, load_config, save_config


@click.command()
def login() -> None:
    """Configure your Fellow workspace and API key."""
    subdomain = click.prompt("Workspace subdomain", type=str).strip()
    url = f"https://{subdomain}.fellow.app/settings/api-keys"
    click.echo(f"Opening {url} ...")
    try:
        webbrowser.open(url)
    except Exception:
        click.echo("(Couldn't auto-open the browser. Open the URL above manually.)")
    api_key = click.prompt("API key", type=str, hide_input=True).strip()

    client = FellowClient(subdomain=subdomain, api_key=api_key)
    try:
        me = client.get_me()
    except AuthError as e:
        click.echo(f"Login failed: {e}", err=True)
        click.echo("Double-check your subdomain and API key.", err=True)
        sys.exit(2)
    except FellowError as e:
        click.echo(f"Login failed: {e}", err=True)
        sys.exit(2)

    save_config(Config(subdomain=subdomain, api_key=api_key))
    user = me.get("user", {})
    click.echo(f"✓ Authenticated as {user.get('email', '?')}")
    click.echo(f"✓ Saved to {_config_path_display()}")


def _config_path_display() -> str:
    import os
    from fellowai.config import _config_path  # type: ignore[attr-defined]
    return str(_config_path()).replace(os.path.expanduser("~"), "~")


@click.command()
def logout() -> None:
    """Delete stored configuration."""
    delete_config()
    click.echo("Logged out.")


@click.command()
def me() -> None:
    """Show authenticated identity and workspace."""
    try:
        cfg = load_config()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)

    client = FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)
    try:
        m = client.get_me()
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    user = m.get("user", {})
    ws = m.get("workspace", {})
    last4 = cfg.api_key[-4:] if len(cfg.api_key) >= 4 else "????"
    click.echo(f"{user.get('email', '?')}  workspace: {ws.get('subdomain', '?')}  key: ...{last4}")
```

- [ ] **Step 4: Wire commands into `src/fellowai/cli.py`**

Replace the placeholder `login`/`logout`/`me` definitions with imports + registration:

```python
import click

from fellowai import __version__
from fellowai.commands.auth import login, logout, me


@click.group()
@click.version_option(__version__, prog_name="fellowai")
def cli() -> None:
    """Unofficial CLI for Fellow.ai's developer API."""


cli.add_command(login)
cli.add_command(logout)
cli.add_command(me)


@cli.group()
def recordings() -> None:
    """Recording operations."""


@cli.group()
def notes() -> None:
    """Note operations."""


@cli.group(name="action-items")
def action_items() -> None:
    """Action item operations."""
```

- [ ] **Step 5: Run tests, expect pass**

Run: `pytest tests/test_commands/test_auth.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/fellowai/commands/ src/fellowai/cli.py tests/test_commands/
git commit -m "feat(commands): login, logout, me with validation against /me endpoint"
```

---

### Task 10: Recordings commands — list, get, export

**Files:**
- Modify: `src/fellowai/cli.py`
- Create: `src/fellowai/commands/recordings.py`
- Create: `tests/test_commands/test_recordings.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_commands/test_recordings.py`:
```python
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
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
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
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([])
        runner.invoke(cli, ["recordings", "list", "--since", "2026-05-01", "--json"])
    call_kwargs = MockClient.return_value.list_recordings.call_args.kwargs
    assert call_kwargs["filters"]["created_at_start"] == "2026-05-01T00:00:00Z"


def test_list_recordings_with_transcript(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([])
        runner.invoke(cli, ["recordings", "list", "--with-transcript", "--json"])
    kwargs = MockClient.return_value.list_recordings.call_args.kwargs
    assert kwargs["include"]["transcript"] is True


def test_get_recording_outputs_markdown_by_default(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
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
    runner = CliRunner(mix_stderr=False)
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
        MockClient.return_value.list_recordings.return_value = iter([
            {"id": "r1", "title": "T", "media_url": None}
        ])
        result = runner.invoke(
            cli, ["recordings", "list", "--with-media", "--json"]
        )
    assert result.exit_code == 0
    assert "not privileged" in (result.stderr or "")


def test_export_to_stdout_concatenates_markdown(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
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
    with patch("fellowai.commands.recordings.FellowClient") as MockClient:
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
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_commands/test_recordings.py -v`
Expected: FAIL on import

- [ ] **Step 3: Implement `src/fellowai/commands/recordings.py`**

```python
"""Recordings commands: list, get, export."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from fellowai.client import FellowClient, FellowError
from fellowai.config import ConfigError, load_config
from fellowai.output import emit, render_recording_markdown
from fellowai.time_parse import parse_since


def _client() -> FellowClient:
    try:
        cfg = load_config()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    return FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)


def _build_filters(since: str | None, until: str | None, updated_since: str | None,
                   channel: str | None, title: str | None, event: str | None) -> dict:
    filters: dict[str, Any] = {}
    if since:
        filters["created_at_start"] = parse_since(since)
    if until:
        filters["created_at_end"] = parse_since(until)
    if updated_since:
        filters["updated_at_start"] = parse_since(updated_since)
    if channel:
        filters["channel_id"] = channel
    if title:
        filters["title"] = title
    if event:
        filters["event_guid"] = event
    return filters


def _build_include(with_transcript: bool, with_ai_notes: bool, with_media: bool) -> dict:
    include: dict[str, Any] = {}
    if with_transcript:
        include["transcript"] = True
    if with_ai_notes:
        include["ai_notes"] = True
    if with_media:
        include["media_url"] = True
    return include


def _warn_media_null(items: list[dict], requested_media: bool) -> None:
    if not requested_media:
        return
    if any(i.get("media_url") is None for i in items):
        click.echo(
            "Warning: media_url was requested but returned null for some recordings. "
            "Your API key isn't privileged. Ask a workspace admin to provision a "
            "privileged key to download recording audio/video.",
            err=True,
        )


# --- list ---


@click.command(name="list")
@click.option("--since")
@click.option("--until")
@click.option("--updated-since")
@click.option("--channel")
@click.option("--title")
@click.option("--event")
@click.option("--with-transcript", is_flag=True)
@click.option("--with-ai-notes", is_flag=True)
@click.option("--with-media", is_flag=True)
@click.option("--limit", type=int, default=50)
@click.option("--page-size", type=click.IntRange(1, 50), default=20)
@click.option("--json", "format_override", flag_value="json")
def recordings_list(
    since: str | None, until: str | None, updated_since: str | None,
    channel: str | None, title: str | None, event: str | None,
    with_transcript: bool, with_ai_notes: bool, with_media: bool,
    limit: int, page_size: int, format_override: str | None,
) -> None:
    """List recordings."""
    client = _client()
    filters = _build_filters(since, until, updated_since, channel, title, event)
    include = _build_include(with_transcript, with_ai_notes, with_media)
    try:
        items = list(client.list_recordings(
            filters=filters or None, include=include or None,
            limit=limit, page_size=page_size,
        ))
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    _warn_media_null(items, with_media)
    emit(items, shape="list",
         columns=["id", "title", "started_at"],
         format_override=format_override,
         empty_message="No recordings.")


# --- get ---


@click.command(name="get")
@click.argument("recording_id")
@click.option("--no-transcript", is_flag=True)
@click.option("--no-ai-notes", is_flag=True)
@click.option("--no-media", is_flag=True)
@click.option("--json", "format_override", flag_value="json")
@click.option("--md", "format_override", flag_value="md")
def recordings_get(
    recording_id: str,
    no_transcript: bool, no_ai_notes: bool, no_media: bool,
    format_override: str | None,
) -> None:
    """Retrieve a single recording (transcript and AI notes included by default)."""
    client = _client()
    try:
        rec = client.get_recording(recording_id)
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    if no_transcript:
        rec["transcript"] = None
    if no_ai_notes:
        rec["ai_notes"] = None
    if no_media:
        rec["media_url"] = None

    emit(rec, shape="document",
         markdown_renderer=render_recording_markdown,
         format_override=format_override or "md")


# --- export ---


@click.command(name="export")
@click.option("--since")
@click.option("--until")
@click.option("--updated-since")
@click.option("--channel")
@click.option("--title")
@click.option("--event")
@click.option("--with-transcript", is_flag=True)
@click.option("--with-ai-notes", is_flag=True)
@click.option("--with-media", is_flag=True)
@click.option("--limit", type=int, default=200)
@click.option("--page-size", type=click.IntRange(1, 50), default=50)
@click.option("--format", "fmt", type=click.Choice(["json", "md", "both"]), default="md")
@click.option("--to", "destination", required=True)
def recordings_export(
    since: str | None, until: str | None, updated_since: str | None,
    channel: str | None, title: str | None, event: str | None,
    with_transcript: bool, with_ai_notes: bool, with_media: bool,
    limit: int, page_size: int, fmt: str, destination: str,
) -> None:
    """Export recordings to disk or stdout."""
    if destination == "-" and fmt == "both":
        click.echo("Cannot export 'both' formats to stdout — pick json or md.", err=True)
        sys.exit(1)

    client = _client()
    filters = _build_filters(since, until, updated_since, channel, title, event)
    include = _build_include(with_transcript, with_ai_notes, with_media)
    try:
        items = list(client.list_recordings(
            filters=filters or None, include=include or None,
            limit=limit, page_size=page_size,
        ))
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    _warn_media_null(items, with_media)

    if destination == "-":
        _write_stream(sys.stdout, items, fmt)
    else:
        outdir = Path(destination)
        outdir.mkdir(parents=True, exist_ok=True)
        for rec in items:
            rec_id = rec["id"]
            if fmt in ("json", "both"):
                (outdir / f"{rec_id}.json").write_text(json.dumps(rec, default=str))
            if fmt in ("md", "both"):
                (outdir / f"{rec_id}.md").write_text(render_recording_markdown(rec))


def _write_stream(stream, items: list[dict], fmt: str) -> None:
    if fmt == "json":
        stream.write(json.dumps(items, default=str) + "\n")
        return
    for i, rec in enumerate(items):
        if i:
            stream.write("\n---\n\n")
        stream.write(render_recording_markdown(rec))


def register(group: click.Group) -> None:
    group.add_command(recordings_list)
    group.add_command(recordings_get)
    group.add_command(recordings_export)
```

- [ ] **Step 4: Wire into `cli.py`**

Replace the `recordings` group in `src/fellowai/cli.py`:

```python
from fellowai.commands import recordings as recordings_cmds

@cli.group()
def recordings() -> None:
    """Recording operations."""


recordings_cmds.register(recordings)
```

- [ ] **Step 5: Run tests, expect pass**

Run: `pytest tests/test_commands/test_recordings.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add src/fellowai/commands/recordings.py src/fellowai/cli.py tests/test_commands/test_recordings.py
git commit -m "feat(commands): recordings list/get/export with filters, includes, formats"
```

---

### Task 11: Notes commands — list, get, export

**Files:**
- Create: `src/fellowai/commands/notes.py`
- Modify: `src/fellowai/cli.py`
- Create: `tests/test_commands/test_notes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_commands/test_notes.py`:
```python
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
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_commands/test_notes.py -v`
Expected: FAIL on import

- [ ] **Step 3: Implement `src/fellowai/commands/notes.py`**

```python
"""Notes commands: list, get, export."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from fellowai.client import FellowClient, FellowError
from fellowai.config import ConfigError, load_config
from fellowai.output import emit, render_note_markdown
from fellowai.time_parse import parse_since


def _client() -> FellowClient:
    try:
        cfg = load_config()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    return FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)


def _build_filters(since: str | None, until: str | None) -> dict:
    filters: dict[str, Any] = {}
    if since:
        filters["created_at_start"] = parse_since(since)
    if until:
        filters["created_at_end"] = parse_since(until)
    return filters


def _build_include(with_content: bool, with_attendees: bool) -> dict:
    include: dict[str, Any] = {}
    if with_content:
        include["content_markdown"] = True
    if with_attendees:
        include["event_attendees"] = True
    return include


@click.command(name="list")
@click.option("--since")
@click.option("--until")
@click.option("--with-content", is_flag=True)
@click.option("--with-attendees", is_flag=True)
@click.option("--limit", type=int, default=50)
@click.option("--page-size", type=click.IntRange(1, 50), default=20)
@click.option("--json", "format_override", flag_value="json")
def notes_list(since, until, with_content, with_attendees, limit, page_size, format_override):
    """List notes."""
    client = _client()
    filters = _build_filters(since, until)
    include = _build_include(with_content, with_attendees)
    try:
        items = list(client.list_notes(
            filters=filters or None, include=include or None,
            limit=limit, page_size=page_size,
        ))
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    emit(items, shape="list",
         columns=["id", "title", "event_start"],
         format_override=format_override,
         empty_message="No notes.")


@click.command(name="get")
@click.argument("note_id")
@click.option("--json", "format_override", flag_value="json")
@click.option("--md", "format_override", flag_value="md")
def notes_get(note_id, format_override):
    """Retrieve a single note (content and attendees included by default)."""
    client = _client()
    try:
        note = client.get_note(note_id)
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    emit(note, shape="document",
         markdown_renderer=render_note_markdown,
         format_override=format_override or "md")


@click.command(name="export")
@click.option("--since")
@click.option("--until")
@click.option("--with-content", is_flag=True)
@click.option("--with-attendees", is_flag=True)
@click.option("--limit", type=int, default=200)
@click.option("--page-size", type=click.IntRange(1, 50), default=50)
@click.option("--format", "fmt", type=click.Choice(["json", "md", "both"]), default="md")
@click.option("--to", "destination", required=True)
def notes_export(since, until, with_content, with_attendees, limit, page_size, fmt, destination):
    """Export notes to disk or stdout."""
    if destination == "-" and fmt == "both":
        click.echo("Cannot export 'both' formats to stdout — pick json or md.", err=True)
        sys.exit(1)

    client = _client()
    filters = _build_filters(since, until)
    include = _build_include(with_content, with_attendees)
    try:
        items = list(client.list_notes(
            filters=filters or None, include=include or None,
            limit=limit, page_size=page_size,
        ))
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    if destination == "-":
        if fmt == "json":
            sys.stdout.write(json.dumps(items, default=str) + "\n")
        else:
            for i, n in enumerate(items):
                if i:
                    sys.stdout.write("\n---\n\n")
                sys.stdout.write(render_note_markdown(n))
        return

    outdir = Path(destination)
    outdir.mkdir(parents=True, exist_ok=True)
    for n in items:
        nid = n["id"]
        if fmt in ("json", "both"):
            (outdir / f"{nid}.json").write_text(json.dumps(n, default=str))
        if fmt in ("md", "both"):
            (outdir / f"{nid}.md").write_text(render_note_markdown(n))


def register(group: click.Group) -> None:
    group.add_command(notes_list)
    group.add_command(notes_get)
    group.add_command(notes_export)
```

- [ ] **Step 4: Wire into `cli.py`**

Add to `src/fellowai/cli.py`:

```python
from fellowai.commands import notes as notes_cmds

@cli.group()
def notes() -> None:
    """Note operations."""


notes_cmds.register(notes)
```

- [ ] **Step 5: Run tests, expect pass**

Run: `pytest tests/test_commands/test_notes.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/fellowai/commands/notes.py src/fellowai/cli.py tests/test_commands/test_notes.py
git commit -m "feat(commands): notes list/get/export"
```

---

### Task 12: Action-items commands — list, get, complete, uncomplete, archive

**Files:**
- Create: `src/fellowai/commands/action_items.py`
- Modify: `src/fellowai/cli.py`
- Create: `tests/test_commands/test_action_items.py`

- [ ] **Step 1: Write failing tests (read + write commands; `pick` is Task 13)**

Create `tests/test_commands/test_action_items.py`:
```python
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


def test_list_action_items_default_scope_mine(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.action_items.FellowClient") as MockClient:
        MockClient.return_value.list_action_items.return_value = iter([])
        runner.invoke(cli, ["action-items", "list", "--json"])
    kwargs = MockClient.return_value.list_action_items.call_args.kwargs
    assert kwargs["filters"]["scope"] == "assigned_to_me"


def test_list_action_items_filter_flags(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.action_items.FellowClient") as MockClient:
        MockClient.return_value.list_action_items.return_value = iter([])
        runner.invoke(cli, [
            "action-items", "list",
            "--scope", "all", "--not-completed", "--archived",
            "--ai-detected", "--order", "due", "--json",
        ])
    kwargs = MockClient.return_value.list_action_items.call_args.kwargs
    assert kwargs["filters"] == {
        "scope": "all", "completed": False, "archived": True, "ai_detected": True
    }
    assert kwargs["order_by"] == "due_date"


def test_list_action_items_since_client_side_filter(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    items = [
        {"id": "old", "text": "x", "status": "Incomplete", "created_at": "2026-04-01T00:00:00Z"},
        {"id": "new", "text": "y", "status": "Incomplete", "created_at": "2026-05-15T00:00:00Z"},
    ]
    runner = CliRunner()
    with patch("fellowai.commands.action_items.FellowClient") as MockClient:
        MockClient.return_value.list_action_items.return_value = iter(items)
        result = runner.invoke(cli, [
            "action-items", "list", "--since", "2026-05-01", "--json"
        ])
    data = json.loads(result.output)
    assert [i["id"] for i in data] == ["new"]


def test_get_action_item_card_on_tty(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.action_items.FellowClient") as MockClient:
        MockClient.return_value.get_action_item.return_value = {
            "id": "x", "text": "Email Bob", "status": "Incomplete",
            "due_date": None, "assignees": [{"full_name": "K"}], "ai_detected": False,
        }
        result = runner.invoke(cli, ["action-items", "get", "x"])
    assert result.exit_code == 0
    assert "Email Bob" in result.output


def test_complete_with_yes_calls_api(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.action_items.FellowClient") as MockClient:
        MockClient.return_value.set_action_item_completed.return_value = {
            "id": "x", "status": "Done", "text": "T"
        }
        result = runner.invoke(cli, ["action-items", "complete", "x", "--yes"])
    assert result.exit_code == 0
    assert "Done" in result.output
    MockClient.return_value.set_action_item_completed.assert_called_once_with("x", True)


def test_complete_without_yes_prompts_and_aborts_on_no(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.action_items.FellowClient") as MockClient:
        result = runner.invoke(cli, ["action-items", "complete", "x"], input="n\n")
    assert result.exit_code == 1
    MockClient.return_value.set_action_item_completed.assert_not_called()


def test_uncomplete_with_yes(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.action_items.FellowClient") as MockClient:
        MockClient.return_value.set_action_item_completed.return_value = {
            "id": "x", "status": "Incomplete", "text": "T"
        }
        result = runner.invoke(cli, ["action-items", "uncomplete", "x", "--yes"])
    assert result.exit_code == 0
    MockClient.return_value.set_action_item_completed.assert_called_once_with("x", False)


def test_archive_with_yes(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.action_items.FellowClient") as MockClient:
        MockClient.return_value.archive_action_item.return_value = {
            "id": "x", "status": "Archived", "text": "T"
        }
        result = runner.invoke(cli, ["action-items", "archive", "x", "--yes"])
    assert result.exit_code == 0
    assert "Archived" in result.output
    MockClient.return_value.archive_action_item.assert_called_once_with("x")
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_commands/test_action_items.py -v`
Expected: FAIL on import

- [ ] **Step 3: Implement `src/fellowai/commands/action_items.py` (read + write commands only — `pick` in Task 13)**

```python
"""Action-items commands: list, get, complete, uncomplete, archive."""

from __future__ import annotations

import sys
from typing import Any

import click

from fellowai.client import FellowClient, FellowError
from fellowai.config import ConfigError, load_config
from fellowai.output import emit, render_action_item_card
from fellowai.time_parse import parse_since


def _client() -> FellowClient:
    try:
        cfg = load_config()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    return FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)


_SCOPE_MAP = {"mine": "assigned_to_me", "others": "assigned_to_others", "all": "all"}
_ORDER_MAP = {"newest": "created_at_desc", "oldest": "created_at_asc", "due": "due_date"}


def _build_filters(scope: str, completed: bool | None,
                   archived: bool | None, ai_detected: bool | None) -> dict:
    filters: dict[str, Any] = {"scope": _SCOPE_MAP[scope]}
    if completed is not None:
        filters["completed"] = completed
    if archived is not None:
        filters["archived"] = archived
    if ai_detected is not None:
        filters["ai_detected"] = ai_detected
    return filters


@click.command(name="list")
@click.option("--scope", type=click.Choice(["mine", "others", "all"]), default="mine")
@click.option("--completed/--not-completed", "completed", default=None)
@click.option("--archived/--not-archived", "archived", default=None)
@click.option("--ai-detected/--not-ai-detected", "ai_detected", default=None)
@click.option("--order", "order", type=click.Choice(["newest", "oldest", "due"]), default=None)
@click.option("--since", help="Filter client-side on created_at (no server-side filter)")
@click.option("--limit", type=int, default=50)
@click.option("--page-size", type=click.IntRange(1, 50), default=20)
@click.option("--json", "format_override", flag_value="json")
def ai_list(scope, completed, archived, ai_detected, order, since, limit, page_size, format_override):
    """List action items."""
    client = _client()
    filters = _build_filters(scope, completed, archived, ai_detected)
    order_by = _ORDER_MAP[order] if order else None
    try:
        items = list(client.list_action_items(
            filters=filters, order_by=order_by, limit=limit, page_size=page_size,
        ))
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    if since:
        cutoff = parse_since(since)
        items = [i for i in items if (i.get("created_at") or "") >= cutoff]

    emit(items, shape="list",
         columns=["id", "text", "status", "due_date"],
         format_override=format_override,
         empty_message="No action items.")


@click.command(name="get")
@click.argument("action_item_id")
@click.option("--json", "format_override", flag_value="json")
def ai_get(action_item_id, format_override):
    """Retrieve a single action item."""
    client = _client()
    try:
        item = client.get_action_item(action_item_id)
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    emit(item, shape="card",
         card_renderer=render_action_item_card,
         format_override=format_override)


def _confirm_or_abort(message: str, yes: bool) -> None:
    if yes:
        return
    if not click.confirm(message, default=False):
        click.echo("Aborted.")
        sys.exit(1)


@click.command(name="complete")
@click.argument("action_item_id")
@click.option("--yes", is_flag=True)
@click.option("--json", "format_override", flag_value="json")
def ai_complete(action_item_id, yes, format_override):
    """Mark an action item Done."""
    _confirm_or_abort(f"Mark {action_item_id} Done?", yes)
    client = _client()
    try:
        item = client.set_action_item_completed(action_item_id, True)
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    if format_override == "json":
        emit(item, shape="card", format_override="json")
    else:
        click.echo(f"✓ Marked Done: {item.get('text', action_item_id)}")


@click.command(name="uncomplete")
@click.argument("action_item_id")
@click.option("--yes", is_flag=True)
@click.option("--json", "format_override", flag_value="json")
def ai_uncomplete(action_item_id, yes, format_override):
    """Mark an action item Incomplete."""
    _confirm_or_abort(f"Mark {action_item_id} Incomplete?", yes)
    client = _client()
    try:
        item = client.set_action_item_completed(action_item_id, False)
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    if format_override == "json":
        emit(item, shape="card", format_override="json")
    else:
        click.echo(f"✓ Marked Incomplete: {item.get('text', action_item_id)}")


@click.command(name="archive")
@click.argument("action_item_id")
@click.option("--yes", is_flag=True)
@click.option("--json", "format_override", flag_value="json")
def ai_archive(action_item_id, yes, format_override):
    """Archive an action item (one-way; unarchive only via Fellow UI)."""
    _confirm_or_abort(
        f"Archive {action_item_id}? This is one-way — unarchive is only available in the Fellow UI.",
        yes,
    )
    client = _client()
    try:
        item = client.archive_action_item(action_item_id)
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    if format_override == "json":
        emit(item, shape="card", format_override="json")
    else:
        click.echo(f"✓ Archived: {item.get('text', action_item_id)}")


def register(group: click.Group) -> None:
    group.add_command(ai_list)
    group.add_command(ai_get)
    group.add_command(ai_complete)
    group.add_command(ai_uncomplete)
    group.add_command(ai_archive)
```

- [ ] **Step 4: Wire into `cli.py`**

Add to `src/fellowai/cli.py`:

```python
from fellowai.commands import action_items as ai_cmds

@cli.group(name="action-items")
def action_items() -> None:
    """Action item operations."""


ai_cmds.register(action_items)
```

- [ ] **Step 5: Run tests, expect pass**

Run: `pytest tests/test_commands/test_action_items.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add src/fellowai/commands/action_items.py src/fellowai/cli.py tests/test_commands/test_action_items.py
git commit -m "feat(commands): action-items list/get/complete/uncomplete/archive"
```

---

### Task 13: Action-items interactive picker

**Files:**
- Modify: `src/fellowai/commands/action_items.py`
- Modify: `tests/test_commands/test_action_items.py`

The picker can't be tested via Click's CliRunner alone — `questionary` reads from a real tty. The strategy: mock `questionary.checkbox(...).ask()` to return a chosen subset.

- [ ] **Step 1: Append failing tests**

Append to `tests/test_commands/test_action_items.py`:
```python
def test_pick_emits_selected_as_json(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    items = [
        {"id": "a", "text": "First", "status": "Incomplete"},
        {"id": "b", "text": "Second", "status": "Incomplete"},
        {"id": "c", "text": "Third", "status": "Incomplete"},
    ]
    with patch("fellowai.commands.action_items.FellowClient") as MockClient, \
         patch("fellowai.commands.action_items._prompt_selection") as MockPrompt:
        MockClient.return_value.list_action_items.return_value = iter(items)
        # Simulate user selecting items 0 and 2
        MockPrompt.return_value = [items[0], items[2]]
        result = runner.invoke(cli, ["action-items", "pick", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert [i["id"] for i in data] == ["a", "c"]


def test_pick_cancel_exits_1(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    items = [{"id": "a", "text": "First", "status": "Incomplete"}]
    with patch("fellowai.commands.action_items.FellowClient") as MockClient, \
         patch("fellowai.commands.action_items._prompt_selection") as MockPrompt:
        MockClient.return_value.list_action_items.return_value = iter(items)
        MockPrompt.return_value = None  # user pressed q / Ctrl-C
        result = runner.invoke(cli, ["action-items", "pick"])
    assert result.exit_code == 1
```

- [ ] **Step 2: Run tests, expect failure**

Run: `pytest tests/test_commands/test_action_items.py::test_pick_emits_selected_as_json -v`
Expected: FAIL

- [ ] **Step 3: Add the `pick` command and `_prompt_selection` helper**

Append to `src/fellowai/commands/action_items.py` (before `register`):

```python
def _prompt_selection(items: list[dict]) -> list[dict] | None:
    """Open a questionary checkbox prompt; return selected items, or None on cancel."""
    import questionary
    choices = [
        questionary.Choice(
            title=f"{i['text']}  [{i.get('status', '?')}]",
            value=i,
        )
        for i in items
    ]
    answer = questionary.checkbox(
        "Select action items (space to toggle, enter to confirm)",
        choices=choices,
    ).ask()
    if answer is None:
        return None
    return answer


@click.command(name="pick")
@click.option("--scope", type=click.Choice(["mine", "others", "all"]), default="mine")
@click.option("--completed/--not-completed", "completed", default=False)
@click.option("--archived/--not-archived", "archived", default=False)
@click.option("--ai-detected/--not-ai-detected", "ai_detected", default=None)
@click.option("--limit", type=int, default=50)
@click.option("--page-size", type=click.IntRange(1, 50), default=20)
@click.option("--json", "format_override", flag_value="json")
def ai_pick(scope, completed, archived, ai_detected, limit, page_size, format_override):
    """Interactively select action items, emit JSON of selections to stdout."""
    client = _client()
    filters = _build_filters(scope, completed, archived, ai_detected)
    try:
        items = list(client.list_action_items(filters=filters, limit=limit, page_size=page_size))
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    if not items:
        click.echo("No action items to pick from.", err=True)
        sys.exit(1)

    selected = _prompt_selection(items)
    if not selected:
        sys.exit(1)

    emit(selected, shape="list", columns=["id", "text"], format_override="json")
```

Add `ai_pick` to the `register` function:

```python
def register(group: click.Group) -> None:
    group.add_command(ai_list)
    group.add_command(ai_get)
    group.add_command(ai_pick)
    group.add_command(ai_complete)
    group.add_command(ai_uncomplete)
    group.add_command(ai_archive)
```

- [ ] **Step 4: Run tests, expect pass**

Run: `pytest tests/test_commands/test_action_items.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/fellowai/commands/action_items.py tests/test_commands/test_action_items.py
git commit -m "feat(commands): action-items pick — interactive TUI emitting JSON on stdout"
```

---

## Phase 5 — Skill, docs, release

### Task 14: Global `--debug` flag and friendly traceback suppression

**Files:**
- Modify: `src/fellowai/cli.py`
- Modify: every command file (small change: read debug from context, raise instead of swallowing)
- Create: `tests/test_commands/test_debug.py`

The spec requires: without `--debug`, errors are sentence-shaped, never tracebacks; with `--debug`, the underlying traceback and HTTP details go to stderr.

- [ ] **Step 1: Write failing tests**

Create `tests/test_commands/test_debug.py`:
```python
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
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_commands/test_debug.py -v`
Expected: FAIL on `--debug` not recognized

- [ ] **Step 3: Add `--debug` to the top-level cli group**

Replace the `cli` definition in `src/fellowai/cli.py`:

```python
@click.group()
@click.version_option(__version__, prog_name="fellowai")
@click.option("--debug", is_flag=True, help="Show tracebacks and HTTP details on errors.")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """Unofficial CLI for Fellow.ai's developer API."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
```

- [ ] **Step 4: Add a shared helper for error handling**

Create a new module `src/fellowai/errors.py`:

```python
"""Shared error-to-CLI mapping."""

from __future__ import annotations

import sys
import traceback

import click

from fellowai.client import FellowError
from fellowai.config import ConfigError


def handle(error: Exception) -> None:
    """Print a sentence-shaped error or a traceback depending on --debug. Exits 2."""
    ctx = click.get_current_context(silent=True)
    debug = bool(ctx.obj.get("debug")) if (ctx and ctx.obj) else False

    if debug:
        traceback.print_exc(file=sys.stderr)
    else:
        if isinstance(error, (FellowError, ConfigError)):
            click.echo(f"Error: {error}", err=True)
        else:
            click.echo(f"Unexpected error: {error}. Re-run with --debug for details.", err=True)
    sys.exit(2)
```

- [ ] **Step 5: Replace ad-hoc error printouts in every command file**

In `src/fellowai/commands/recordings.py`, `notes.py`, `action_items.py`, and `auth.py` (for `me`), replace the existing `except FellowError as e: click.echo(...); sys.exit(2)` blocks with:

```python
    except (FellowError, ConfigError) as e:
        from fellowai.errors import handle
        handle(e)
```

(Update each command's `try/except` to catch both `FellowError` and `ConfigError` where appropriate, and delegate to `handle`.)

Also remove the local `ConfigError` handling in `_client()` helpers — let it propagate to the per-command handler.

- [ ] **Step 6: Run tests, expect pass**

Run: `pytest tests/test_commands/test_debug.py -v && pytest -v`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/fellowai/cli.py src/fellowai/errors.py src/fellowai/commands/ tests/test_commands/test_debug.py
git commit -m "feat(cli): global --debug flag with traceback fallback; shared error handler"
```

---

### Task 15: SKILL.md bundling + `install-skill` command

**Files:**
- Create: `src/fellowai/SKILL.md`
- Modify: `src/fellowai/commands/auth.py`
- Modify: `src/fellowai/cli.py`
- Modify: `pyproject.toml` (include SKILL.md in wheel)
- Create: `tests/test_commands/test_install_skill.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_commands/test_install_skill.py`:
```python
from pathlib import Path

import pytest
from click.testing import CliRunner

from fellowai.cli import cli


def test_install_skill_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["install-skill"])
    assert result.exit_code == 0
    skill_file = tmp_path / ".claude" / "skills" / "fellowai" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text()
    assert "fellowai" in content
    assert "fellowai recordings export" in content
```

- [ ] **Step 2: Run, expect failure**

Run: `pytest tests/test_commands/test_install_skill.py -v`
Expected: FAIL

- [ ] **Step 3: Create the bundled SKILL.md**

Create `src/fellowai/SKILL.md`:

```markdown
---
name: fellowai
description: Use when accessing Fellow.ai meeting data — recordings,
  transcripts, AI summaries, notes, action items. Don't use for
  non-Fellow meeting data. For semantic search across meetings,
  prefer Fellow's MCP server instead.
---

# fellowai

CLI for Fellow.ai's developer API. Installed command: `fellowai`.
Run `fellowai --help` for the current surface.

## When to use this vs Fellow's MCP server

- **MCP**: natural-language questions, semantic search across meetings
- **This CLI**: scripted exports, pipelines, action-item write ops,
  audio download, anything outside an MCP-aware chat client

## Common patterns

Pipe recent transcripts to an LLM:
    fellowai recordings export --since 7d --with-transcript \
      --format md --to - | <llm command>

Get the AI-generated summary of one meeting as markdown:
    fellowai recordings get <id>

Select action items interactively, emit JSON:
    fellowai action-items pick --scope mine --not-completed

List recordings as JSON (auto when piped):
    fellowai recordings list --since 7d | jq '.[].title'

Mark an action item complete:
    fellowai action-items complete <id> --yes

## Output rules

- TTY: pretty tables for lists, markdown for documents
- Piped: JSON for lists, markdown for documents
- `--json` and `--md` force a format

## Error recovery

- 401 ("API key isn't valid") → run `fellowai login`
- `--with-media` returns null (with stderr warning) → API key isn't
  privileged; ask a workspace admin to provision one
- 429 → wait; rate limits are 3/sec, 10,000/day per key
- Empty result is exit 0, not an error

## What this CLI can't do

- Search meetings (use the MCP)
- List channels or participants (no REST endpoint)
- Webhook management (deferred in v1)
- Delete recordings/notes (deferred in v1)
```

- [ ] **Step 4: Implement `install-skill`**

Add to `src/fellowai/commands/auth.py`:

```python
import importlib.resources as resources
from pathlib import Path


@click.command(name="install-skill")
def install_skill() -> None:
    """Install fellowai's SKILL.md into ~/.claude/skills/fellowai/."""
    skill_text = resources.files("fellowai").joinpath("SKILL.md").read_text()
    home = Path.home()
    dest_dir = home / ".claude" / "skills" / "fellowai"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / "SKILL.md"
    dest_file.write_text(skill_text)
    click.echo(f"✓ Installed skill to {dest_file}")
```

- [ ] **Step 5: Wire into `cli.py`**

Add to `src/fellowai/cli.py`:

```python
from fellowai.commands.auth import install_skill

cli.add_command(install_skill)
```

- [ ] **Step 6: Add SKILL.md to wheel**

In `pyproject.toml`, add under `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/fellowai/SKILL.md" = "fellowai/SKILL.md"
```

(or use `include = ["src/fellowai/SKILL.md"]` if the above doesn't work — Hatch's wheel builder includes package data by default, so this may be a no-op.)

- [ ] **Step 7: Run tests, expect pass**

Run: `pip install -e . && pytest tests/test_commands/test_install_skill.py -v`
Expected: 1 passed

- [ ] **Step 8: Commit**

```bash
git add src/fellowai/SKILL.md src/fellowai/commands/auth.py src/fellowai/cli.py pyproject.toml tests/test_commands/test_install_skill.py
git commit -m "feat(skill): bundle SKILL.md and add install-skill command"
```

---

### Task 16: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# fellowai

Unofficial CLI for [Fellow.ai](https://fellow.ai)'s developer API. Designed to complement Fellow's MCP server: use the MCP to **ask questions** about meetings; use `fellowai` to **do things** with meeting data — export, automate, manage action items, pipe to LLMs.

## Install

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install fellowai
```

Windows (PowerShell):

```powershell
irm https://astral.sh/uv/install.ps1 | iex
uv tool install fellowai
```

## Quick start

```bash
fellowai login        # prompts for workspace subdomain and API key
fellowai me           # confirms you're authenticated
fellowai recordings list --since 7d
```

To create an API key: in Fellow, **User Settings → Developer API → Generate new key**. Your workspace admin may need to enable the Developer API in Workspace Security first.

## Three sample pipelines

**1. Summarize this week's meetings with an LLM**

```bash
fellowai recordings export --since 7d --with-transcript --format md --to - \
  | llm "summarize the key decisions and risks from these meetings"
```

**2. Interactively pick action items, pipe JSON to something**

```bash
fellowai action-items pick --scope mine --not-completed \
  | jq '.[] | {text, due_date}'
```

**3. Mark a done thing done**

```bash
fellowai action-items complete <id> --yes
```

## Relationship to Fellow's MCP server

Use Fellow's MCP (`https://fellow.app/mcp`) when you want natural-language Q&A or semantic search across meetings — those are things this CLI can't do. Use this CLI for everything else: scripting, automation, write operations, bulk export, action-item workflows.

## What this CLI exposes

| Resource | Commands |
|-|-|
| Auth | `login`, `logout`, `me`, `install-skill` |
| Recordings | `list`, `get`, `export` |
| Notes | `list`, `get`, `export` |
| Action items | `list`, `get`, `pick`, `complete`, `uncomplete`, `archive` |

Run `fellowai <group> --help` for details.

## Output rules

- TTY: pretty tables for lists, markdown for documents
- Piped: JSON for lists, markdown for documents
- `--json` and `--md` force a format

## Status

v0.x — pre-1.0, breaking changes possible at minor bumps. Pin via `uv tool install 'fellowai==0.1.*'` if needed.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with install, quick start, three pipelines, MCP positioning"
```

---

### Task 17: GitHub Actions CI + PyPI publish

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/publish.yml`

- [ ] **Step 1: Create CI workflow**

Create `.github/workflows/ci.yml`:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ["3.10", "3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Lint
        run: ruff check src tests
      - name: Test
        run: pytest -v
      - name: Smoke
        run: fellowai --version
```

- [ ] **Step 2: Create publish workflow (trusted publishing)**

Create `.github/workflows/publish.yml`:
```yaml
name: Publish to PyPI
on:
  push:
    tags: ['v*']

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # for PyPI trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Build
        run: |
          python -m pip install --upgrade pip build
          python -m build
      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 3: Commit**

```bash
git add .github/
git commit -m "ci: add CI matrix and PyPI trusted-publishing workflow"
```

- [ ] **Step 4: Set up PyPI trusted publishing (manual, out of band)**

This is one-time, done in PyPI's web UI after Task 17 is merged:

1. Go to https://pypi.org/manage/account/publishing/
2. Add a pending publisher:
   - PyPI Project Name: `fellowai`
   - Owner: `<your-github-org-or-username>`
   - Repository name: `fellow-cli` (or whatever it ends up as)
   - Workflow filename: `publish.yml`
   - Environment name: (leave blank)
3. To release: `git tag v0.1.0 && git push --tags` — the publish workflow fires.

---

## Acceptance verification

After all tasks complete, run end-to-end against the live API to verify the spec's acceptance criteria:

- [ ] `fellowai login` works (real subdomain + key)
- [ ] `fellowai me` prints identity
- [ ] `fellowai recordings list --since 7d` returns expected data
- [ ] `fellowai recordings get <real-id>` renders transcript and AI notes as markdown
- [ ] `fellowai recordings export --since 7d --with-transcript --format md --to ./out/` writes files
- [ ] `fellowai notes list --since 7d` works
- [ ] `fellowai action-items list --scope mine --not-completed` works
- [ ] `fellowai action-items pick` opens TUI, emits JSON
- [ ] `fellowai action-items complete <id> --yes` toggles status
- [ ] `fellowai action-items uncomplete <id> --yes` reverts
- [ ] `fellowai install-skill` writes to `~/.claude/skills/fellowai/SKILL.md`
- [ ] Empty result exit codes are 0 with `[]` when piped
- [ ] 401 produces a sentence error, never a traceback
- [ ] Wrong subdomain at `login` produces a sentence error

If any verification step fails, write a fix as a follow-up task before declaring v1 done.
