# fellowai — Design Spec

**Date:** 2026-05-16
**Status:** Draft for review (post-API-recon)
**Owner:** Kramer Sharp (primary users: Kramer + Chris, possibly half of Reurbano)
**Command name:** `fellowai`

## Problem

Reurbano uses Fellow.ai for meeting recordings, transcripts, and action items. The official Fellow MCP server is available but has two problems:

1. **Context tax.** MCP tool definitions stay loaded every turn. Seven Fellow tools means a permanent token cost on every Claude Code session, whether or not Fellow is used.
2. **Surface limits.** The MCP exposes a fixed shape; we can't compose its outputs cleanly with Unix pipes, can't batch-export, can't drive an interactive picker.

A CLI fixes both. It costs zero permanent context (the agent reads `--help` only when needed), it composes with standard tools, and we control the surface.

## Goals

- Give Reurbano teammates a cross-platform CLI for Fellow that anyone can install in two commands.
- **Headline use case:** ad-hoc terminal piping for LLM work (`fellowai transcripts export --since 7d --to - | llm ...`).
- Expose exactly what Fellow's REST API exposes — no synthesized features.
- Stay small and durable: do not absorb destinations (ClickUp, Linear, etc.); emit JSON and let other tools consume it.

## Non-goals (v1)

- Write operations against Fellow (action-item updates/creates). Read-mostly; `login`/`logout` are the only state-changing commands.
- Webhook subscription management.
- Watch/poll mode for new meetings.
- Pushing data to other systems (ClickUp, Notion, Linear). Out of scope by design.
- Local caching layer. Defer; add if `transcripts export` over large windows feels slow.

## Distribution

**Public PyPI, installed via `uv tool`.** Identical command on macOS, Linux, and Windows. The CLI contains no secrets — access is gated by each teammate's own Fellow API key at runtime.

```
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install fellowai

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
uv tool install fellowai
```

Teammate doc: those two lines plus `fellowai login`.

## Authentication

**Per-user API key, workspace-scoped subdomain, stored in OS-standard config dir.** Never an environment variable, never a shared workspace key.

Fellow's API base URL is `https://{subdomain}.fellow.app/api/v1/...` — the subdomain identifies the workspace and must be captured at login.

`fellowai login` flow:

1. Prompt for workspace subdomain (`reurbano` if `https://reurbano.fellow.app`).
2. Auto-open `https://{subdomain}.fellow.app/settings/api-keys` in the default browser.
3. Prompt for the pasted API key.
4. Validate by calling a known endpoint (`POST /api/v1/action_items` with `pagination: {limit: 1}`) — confirms both subdomain and key in one call. Bad key/subdomain fails fast with a sentence-shaped error.
5. Write to platform config path (`~/.config/fellowai/config.toml` on Linux, `~/Library/Application Support/fellowai/config.toml` on macOS, `%APPDATA%\fellowai\config.toml` on Windows) via `platformdirs`. File mode 600 on POSIX.

`fellowai logout` deletes the stored config. `fellowai me` prints the active subdomain and a redacted key identifier.

Env-var override: `FELLOWAI_API_KEY` + `FELLOWAI_SUBDOMAIN` for CI/scripts. Documented as advanced use, not the recommended path.

## Command surface

```
fellowai login | logout | me
fellowai install-skill                              # drop SKILL.md into ~/.claude/skills/

fellowai meetings      list | get | export | open
fellowai recent                                     # sugar: meetings list --since 1d
fellowai transcripts   get | export
fellowai summaries     get
fellowai notes         get
fellowai action-items  list | get | pick            # pick = interactive TUI → JSON on stdout
fellowai channels      list | get
fellowai participants  list
fellowai search        "<query>" [--since 30d] [--limit 20]
```

All list commands support:
- `--since <relative-or-absolute>` — `7d`, `2026-04-01`, `2w` (single parser)
- `--channel <name-or-id>`, `--participant <email>` where applicable
- `--limit <n>` (default 50)

All `get` commands take a single resource ID.

All `export` commands take `--to <path | ->` and `--format <json|md|both>`:
- `--to <path>` writes to a directory, one file per resource named `<id>.json` / `<id>.md`. `--format both` writes both files per resource.
- `--to -` writes to stdout. `--format json` emits a JSON array; `--format md` emits concatenated markdown with `---` separators; `--format both` is rejected for stdout (ambiguous concatenation).

`fellowai open <meeting-id>` opens the meeting in the Fellow web UI via the default browser.

`fellowai search` maps to Fellow's native meeting search (confirmed available via the MCP server, exact REST path TBD during implementation).

## Output format rules

| Context | Default |
|-|-|
| List commands on TTY | Pretty table |
| List commands when piped/redirected | JSON array (compact) |
| `get` on document-y resources (transcripts, summaries, notes) | Markdown — TTY and piped both |
| `get` on metadata resources (meetings get, action-items get, channels get) | Pretty "card" on TTY, JSON when piped |
| Any command with `--json` | JSON, overrides above |
| Any command with `--md` | Markdown, overrides above |

TTY detection: `sys.stdout.isatty()`.

## Interactive picker

`fellowai action-items pick` opens a TUI listing recent action items with checkboxes:

- Spacebar toggles selection, arrows navigate, `/` filters by substring
- Enter confirms — prints selected items as JSON array to stdout, exits 0
- `q` cancels — exits 1, nothing printed

Implementation: `questionary` (cross-platform including Windows, no native deps).

Picker is the only TUI in v1. Its sole job: select Fellow items, emit JSON. Destination (ClickUp push, etc.) is a separate tool/skill consuming stdin.

## Error UX

Errors must be sentence-shaped, never tracebacks. Designed for teammates who don't read Python.

Examples of required error sentences:

- **Bad/missing config:** `No Fellow workspace configured. Run 'fellowai login' to set one up.`
- **401/403:** `Your API key isn't valid for this workspace. Run 'fellowai login' to re-authenticate.`
- **Network failure:** `Couldn't reach https://reurbano.fellow.app. Check your internet connection.`
- **Bad ID:** `No meeting with ID 'xyz123' (or you don't have access to it).`
- **Stdin closed during pick:** `Action item picker requires a terminal. Run interactively, or pipe a meeting ID list to '... list' instead.`

`--debug` flag attaches the underlying traceback and HTTP details to stderr for support requests. Without it, never leak a traceback.

Exit codes: 0 success, 1 user-caused (no results, cancelled picker, bad input), 2 system (network, auth, server error).

## Architecture

Python 3.10+, Click for command structure, `httpx` for the API client, `rich` for tables/markdown rendering, `platformdirs` for config paths, `questionary` for the picker. Pure-Python; no native build steps.

```
fellowai/
├── __main__.py             # entrypoint
├── cli.py                  # Click app, command groups
├── config.py               # config load/save, subdomain + key validation
├── client.py               # FellowClient (httpx), auth, pagination, retry, error mapping
├── commands/
│   ├── auth.py             # login, logout, me, install-skill
│   ├── meetings.py
│   ├── transcripts.py
│   ├── summaries.py
│   ├── notes.py
│   ├── action_items.py     # includes interactive pick
│   ├── channels.py
│   ├── participants.py
│   └── search.py
├── output.py               # TTY detection, JSON/table/markdown rendering
└── time_parse.py           # --since parser (relative + absolute)
```

`client.py` is the single point of contact with Fellow's API. Every command goes through it. Pagination, retries (with backoff on 429/5xx), consistent error mapping live there.

`output.py` is the single point of contact with stdout. Every command hands it `(data, shape_hint)`; output.py decides table vs JSON vs markdown based on TTY + flags.

## API client behavior

- Base URL: `https://{subdomain}.fellow.app/api/v1` (subdomain from config).
- Auth header: name TBD during implementation (`X-API-KEY` likely based on search hits; confirm with real key).
- **List endpoints use POST with JSON body** (confirmed for action_items): `{pagination, filters, order_by, include}`. The client exposes a Python iterator that handles pagination internally; commands consume it.
- Retry: 429 honors `Retry-After`; 5xx uses exponential backoff (max 3 retries).
- 401/403 produces the sentence error pointing at `fellowai login`.
- Network errors produce a sentence error; exit 2.
- `--debug` enables `httpx` request/response logging to stderr.

## Privacy & telemetry

**No telemetry. Zero.** No usage pings, no error reporting that leaves the laptop. Important for a meeting-data tool — and a small team doesn't need it.

Local files written by the CLI:
- Config: subdomain + API key (mode 600).
- Cache (when added later): under platform cache dir; never includes raw transcripts unless cache feature is opt-in.
- Exports: wherever `--to` points. User's responsibility.

No file is sent anywhere except direct API calls to `*.fellow.app`.

## Versioning policy

- Pre-1.0: `v0.x`. Breaking changes possible at any minor bump.
- Users who need stability: `uv tool install 'fellowai==0.3.*'`.
- Changelog kept in `CHANGELOG.md`; every release notes any breaking change at the top.
- Cut 1.0 only when the surface has been stable for a month and we're confident in the API.

## Testing

- Unit: every command's argument parsing + output formatter.
- Client: HTTP mocked with `respx`; pagination, retries, error mapping covered.
- E2E: recorded cassettes (`vcr.py`) per command, replayed in CI. Recording requires a workspace key, kept out of CI but rerunnable locally with `tests/record.sh`.

## Agent discoverability

A `SKILL.md` ships inside the package. `fellowai install-skill` copies it into `~/.claude/skills/fellowai/` (or platform equivalent). The skill teaches Claude Code: which commands exist, when to use `--json`, common pipe patterns, error recovery.

Bundling rationale: keeps skill version in lockstep with installed CLI version. Generating SKILL.md from `--help` at install time is a future refinement, not v1.

## What we know vs what we'll confirm in implementation

**Verified from public docs:**
- Workspace-scoped subdomain in URL (`https://{subdomain}.fellow.app/api/v1`).
- `POST /api/v1/action_items` for listing, with body-based pagination/filters/order/include.
- `GET /api/v1/action_item/{id}` for retrieval.
- Per-user API keys, generated in Fellow's User Settings → Developer Tools.
- Permission-aware (API users see only what they can see in the app).
- 90-day audit logging on Fellow's side.

**Strongly implied from the Fellow MCP server's tool list** (the MCP almost certainly wraps the REST API):
- meetings list/get
- meeting transcripts (per meeting)
- meeting summaries (per meeting)
- meeting participants (per meeting)
- channels list/get
- meeting search

For these, the exact REST paths and request shapes will be confirmed during implementation by probing with a real API key. The spec assumes a consistent pattern with the action-items endpoints: lists are POST-with-body, retrievals are GET-by-id.

**Will need to confirm with the live API:**
- Auth header name (`X-API-KEY` vs `Authorization: Bearer`).
- Whether summaries and agendas have first-class endpoints or are nested in the meeting response — if nested, drop `summaries get` and expose via `meetings get --include summary`.
- Exact pagination cursor/token shape.
- Rate limits.
- Assignee filter format (email vs user ID).

**Risk if the API turns out to be narrower than the MCP suggests:** v1 ships fewer commands than the spec lists, and we document what's not yet available. The architecture (single client, single output module, command-per-resource) absorbs this cleanly.

## Out of scope, captured for later

- ClickUp / Linear / Notion push (separate tools or skills consuming `pick` stdout).
- Write operations on action items.
- Watch/poll mode and webhook subscriptions.
- Caching layer.
- Homebrew tap / scoop / winget — layer on top of PyPI later if `uv tool install` friction proves real.
- Generating SKILL.md from `--help` at install time.
