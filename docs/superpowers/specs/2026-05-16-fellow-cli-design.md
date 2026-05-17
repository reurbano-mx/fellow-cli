# fellowai — Design Spec

**Date:** 2026-05-16 (updated after Playwright API recon)
**Status:** Draft for review
**Owner:** Kramer Sharp (primary users: Kramer + Chris, possibly half of Reurbano)
**Command name:** `fellowai`

## Problem

Reurbano uses Fellow.ai for meeting recordings, transcripts, and action items. The official Fellow MCP server is available but has two problems:

1. **Context tax.** MCP tool definitions stay loaded every turn. A permanent token cost on every Claude Code session, whether or not Fellow is used.
2. **Surface limits.** The MCP exposes a fixed shape; we can't compose its outputs cleanly with Unix pipes, can't batch-export, can't drive an interactive picker.

A CLI fixes both. It costs zero permanent context (the agent reads `--help` only when needed), it composes with standard tools, and we control the surface.

## Goals

- Give Reurbano teammates a cross-platform CLI for Fellow that anyone can install in two commands.
- **Headline use case:** ad-hoc terminal piping for LLM work (`fellowai recordings export --since 7d --include transcript --to - | llm ...`).
- Expose exactly what Fellow's REST API exposes — no synthesized features.
- Stay small and durable: do not absorb destinations (ClickUp, Linear, etc.); emit JSON and let other tools consume it.

## Non-goals (v1)

- Recording deletion and note deletion (`DELETE /recording/{id}`, `DELETE /note/{id}` exist; dangerous; defer until needed).
- Webhook management (Create/Retrieve/Update/Delete/List webhooks exist in the API; useful but bigger surface; defer).
- Watch/poll mode (re-implement via cron + `recordings list --since 1h --json` once we have it).
- Pushing data to other systems (ClickUp, Notion, Linear). Out of scope by design.
- Local caching layer. Defer.
- Search. The public API has no search endpoint (the MCP server's `search_meetings` is MCP-internal or implemented elsewhere). Not synthesizing one.

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

Confirmed from `developers.fellow.ai/reference/authentication-1`:

- Header: `X-API-KEY: <key>`
- Base URL: `https://{subdomain}.fellow.app/api/v1`
- Keys are user-scoped, generated in Fellow's User Settings → Developer API (workspace admin must enable the Developer API in Security settings first).
- Access mirrors in-app access: API users only see meetings, recordings, and notes they can already see in Fellow.
- Workspace admins can see key names and last-used timestamps; they cannot see the secret itself.

`fellowai login` flow:

1. Prompt for workspace subdomain (`reurbano` if `https://reurbano.fellow.app`).
2. Auto-open `https://{subdomain}.fellow.app/settings/api-keys` in the default browser.
3. Prompt for the pasted API key.
4. Validate with `GET /api/v1/me` (confirmed endpoint). Bad subdomain/key fails fast with a sentence-shaped error.
5. Write to platform config path (`~/.config/fellowai/config.toml` on Linux, `~/Library/Application Support/fellowai/config.toml` on macOS, `%APPDATA%\fellowai\config.toml` on Windows) via `platformdirs`. File mode 600 on POSIX.

`fellowai logout` deletes the stored config. `fellowai me` calls `GET /me` and prints the authenticated identity plus the active subdomain.

Env-var override for CI/scripts: `FELLOWAI_API_KEY` + `FELLOWAI_SUBDOMAIN`. Documented as advanced, not the recommended path.

## API surface (verified)

The complete public REST API as of 2026-05-16, confirmed via Playwright crawl of `developers.fellow.ai/reference/*`:

| Resource | Operation | Method | Path |
|-|-|-|-|
| Users | Get authenticated user | GET | `/me` |
| Recordings | Retrieve | GET | `/recording/{id}` |
| Recordings | List | POST | `/recordings` |
| Recordings | Delete | DELETE | `/recording/{id}` |
| Notes | Retrieve | GET | `/note/{id}` |
| Notes | List | POST | `/notes` |
| Notes | Delete | DELETE | `/note/{id}` |
| Action Items | Retrieve | GET | `/action_item/{id}` |
| Action Items | List | POST | `/action_items` |
| Action Items | Mark complete | POST | (slug: `mark_action_item_complete`) |
| Action Items | Archive | POST | (slug: `archive_action_item`) |
| Webhooks | Create/Retrieve/Update/Delete/List | POST/GET/PATCH/DELETE/GET | — |

Notable findings:

- **Transcripts and AI summaries are nested fields on the Recording resource**, not separate endpoints. The Recording response includes `transcript`, `ai_notes` (with sub-types: Key Moments, Topics, Action Items, Decisions, free text), `media_url` (pre-signed audio/video URL — requires a *privileged* API key), and metadata (`title`, `started_at`, `ended_at`, `note_id`).
- **The `include` parameter on list/retrieve endpoints controls expensive fields.** Transcript and `ai_notes` are NOT returned by default; you must request them via `include`. This matters for performance — list calls without `include` are fast.
- **Notes are a distinct resource from Recordings.** A Recording's `note_id` links to the corresponding Note. Notes hold the structured/editable meeting note document (agenda, decisions, human-written content).
- **Action items are flat** — not nested in recordings — with their own list/retrieve plus `complete` and `archive` write operations.

## Pagination, rate limits, errors

Confirmed:

- **Pagination is cursor-based**, request body shape: `{ "pagination": { "cursor": null|string, "page_size": 1-50 } }` (default page_size 20). Response wraps results in `{ "page_info": { "cursor": null|string, "page_size": int }, "data": [...] }`. Null cursor in response signals end of results.
- **Rate limits per API key:** 3 requests/second, 10,000 requests/day. Limit exceeded returns HTTP 429 with error code `rate_limited`.
- **Auth failures:** HTTP 401 for missing/invalid key.
- The client honors any `Retry-After` header on 429 and uses exponential backoff on 5xx (max 3 retries).

## Command surface

```
fellowai login | logout | me
fellowai install-skill                                # drop SKILL.md into ~/.claude/skills/

fellowai recordings   list | get | export
fellowai notes        list | get | export
fellowai action-items list | get | pick | complete | archive
```

Common flags on all list commands:

- `--since <relative-or-absolute>` — `7d`, `2026-04-01`, `2w` (single parser; mapped into a `filters` body field)
- `--limit <n>` — total max records returned across all pages (default 50; the client paginates underneath)
- `--page-size <n>` — per-page size for the underlying API call (1–50, default 20)

Resource-specific flags:

- `recordings list/get/export` accept `--include <fields>` — comma-separated subset of `transcript`, `ai_notes`, `media_url`. `media_url` requires a privileged API key; we'll detect the resulting 403 and produce a sentence error if a non-privileged key requests it.
- `action-items list` accepts `--assignee <email|me>`, `--scope <mine|others|all>` (maps to the documented `assigned_to_me`/`assigned_to_others` filter).

`export` for recordings and notes:

- `--to <path | ->` — writes to a directory (one file per resource: `<id>.<ext>`) or stdout (`-`)
- `--format <json|md|both>` — for `--to <path>`: `both` writes `<id>.json` + `<id>.md` per resource. For `--to -`: `both` is rejected (concatenation ambiguous).
- Markdown rendering for a Recording: title + dates + `transcript` (if included) rendered as `[speaker]: text` lines + `ai_notes` rendered with section headers.

`action-items complete <id>` and `archive <id>` are the only write commands in v1. They are confirmed-via-prompt by default (`--yes` to skip). Action-item completion is so naturally part of the picker workflow that read-only v1 would leave the picker half-functional.

`action-items pick` is the interactive TUI:
- Spacebar toggles selection, arrows navigate, `/` filters by substring
- Enter confirms — prints selected items as JSON array to stdout, exits 0
- `q` cancels — exits 1, nothing printed
- Implementation: `questionary` (cross-platform, no native deps)

## Output format rules

| Context | Default |
|-|-|
| List commands on TTY | Pretty table |
| List commands when piped/redirected | JSON array (compact) |
| `get` on Recording or Note (document-y) | Markdown — TTY and piped both |
| `get` on Action Item (metadata) | Pretty card on TTY, JSON when piped |
| Any command with `--json` | JSON, overrides above |
| Any command with `--md` | Markdown, overrides above |

TTY detection: `sys.stdout.isatty()`.

## Error UX

Errors must be sentence-shaped, never tracebacks. Designed for teammates who don't read Python.

Examples of required error sentences:

- **No config:** `No Fellow workspace configured. Run 'fellowai login' to set one up.`
- **401:** `Your API key isn't valid for this workspace. Run 'fellowai login' to re-authenticate.`
- **403 on media_url:** `media_url requires a privileged API key. Ask a workspace admin to provision one, or run without --include media_url.`
- **429:** `Rate limit hit (3/sec, 10,000/day per key). Slow down or wait a minute.`
- **Network failure:** `Couldn't reach https://reurbano.fellow.app. Check your internet connection.`
- **Bad ID:** `No recording with ID 'xyz123' (or you don't have access to it).`
- **Picker without TTY:** `Action item picker requires a terminal. Run interactively, or pipe a JSON list to a downstream tool instead.`

`--debug` attaches the underlying traceback and HTTP details to stderr for support requests. Without it, never leak a traceback.

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
│   ├── recordings.py
│   ├── notes.py
│   └── action_items.py     # includes interactive pick + complete + archive
├── output.py               # TTY detection, JSON/table/markdown rendering
└── time_parse.py           # --since parser (relative + absolute)
```

`client.py` is the single point of contact with Fellow's API. Every command goes through it. Pagination, retries (with backoff on 429/5xx), consistent error mapping live there. Exposes a Python iterator API: `for rec in client.list_recordings(filters=..., include=[...]): ...` — the iterator drives cursor pagination internally and respects `--limit` from the command layer.

`output.py` is the single point of contact with stdout. Every command hands it `(data, shape_hint)`; output.py decides table vs JSON vs markdown based on TTY + flags.

## Privacy & telemetry

**No telemetry. Zero.** No usage pings, no error reporting that leaves the laptop. Important for a meeting-data tool.

Local files written by the CLI:
- Config: subdomain + API key (mode 600).
- Exports: wherever `--to` points. User's responsibility.

No file is sent anywhere except direct API calls to `*.fellow.app`.

## Versioning policy

- Pre-1.0: `v0.x`. Breaking changes possible at any minor bump.
- Users who need stability: `uv tool install 'fellowai==0.3.*'`.
- Changelog kept in `CHANGELOG.md`; every release notes any breaking change at the top.
- Cut 1.0 only when the surface has been stable for a month.

## Testing

- Unit: every command's argument parsing + output formatter.
- Client: HTTP mocked with `respx`; pagination, retries, error mapping covered.
- E2E: recorded cassettes (`vcr.py`) per command, replayed in CI. Recording requires a workspace key, kept out of CI but rerunnable locally with `tests/record.sh`.

## Agent discoverability

A `SKILL.md` ships inside the package. `fellowai install-skill` copies it into `~/.claude/skills/fellowai/`. The skill teaches Claude Code: which commands exist, when to use `--json`, common pipe patterns (`recordings export --include transcript --to - | llm ...`), error recovery (`fellowai login` on 401).

## Open questions to resolve during implementation

These need a real API key to confirm; none block the design:

1. Exact request-body field name for `--since` filtering on each list endpoint (likely `started_after`/`started_before` or similar on Recording).
2. Whether the privileged-vs-non-privileged distinction is determined by the key itself (admin-issued vs user-issued) or by some scope on the request.
3. The exact body parameters for `mark_action_item_complete` and `archive_action_item` (probably just an ID; possibly additional flags).
4. Whether `--include transcript` returns transcript inline or as a sub-URL that needs a second fetch.

## Out of scope, captured for later

- Recording/note deletion (`DELETE` endpoints exist).
- Webhook management (full Create/Retrieve/Update/Delete/List surface exists).
- Watch/poll mode.
- ClickUp / Linear / Notion push (separate tools or skills consuming `pick` stdout).
- Caching layer.
- Homebrew tap / scoop / winget — layer on top of PyPI later if `uv tool install` friction proves real.
- Generating SKILL.md from `--help` at install time.
