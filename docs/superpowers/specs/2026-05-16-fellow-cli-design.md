# fellow-cli — Design Spec

**Date:** 2026-05-16
**Status:** Draft for review
**Owner:** Kramer Sharp

## Problem

Reurbano uses Fellow.ai for meeting recordings, transcripts, and action items. The official Fellow MCP server is available but has two problems:

1. **Context tax.** MCP tool definitions stay loaded every turn. A dozen Fellow tools means a permanent token cost on every Claude Code session, whether or not Fellow is used.
2. **Incomplete surface.** The MCP exposes a subset of Fellow's REST API and lacks bulk/export-shaped operations that are useful for LLM piping.

A CLI fixes both. It costs zero permanent context (the agent reads `--help` only when needed), it composes with standard Unix tools, and we control the exact surface.

## Goals

- Give Reurbano teammates a cross-platform CLI for Fellow that anyone can install in two commands.
- Optimize for LLM piping (`fellow transcripts export --to - | llm ...`) and agent invocation (JSON when piped, pretty when interactive).
- Expose exactly what Fellow's REST API exposes — no synthesized features that obscure where data comes from.
- Stay small and durable: do not absorb destinations (ClickUp, Linear, etc.); emit JSON and let other tools consume it.

## Non-goals (v1)

- Write operations against Fellow (action-item updates/creates). Read-mostly only; `login`/`logout` are the only state-changing commands.
- Full-text search across meetings. Deferred until Fellow ships a native search endpoint.
- Webhook subscription management.
- Watch/poll mode for new meetings.
- Pushing data to other systems (ClickUp, Notion, Linear). Out of scope by design — keep boundary at "Fellow data in, JSON out".

## Distribution

**Public PyPI, installed via `uv tool`.** One install command across macOS, Linux, and Windows. No code-signing pain, no per-OS binary pipeline, no PyPI alternatives needed because the CLI contains no secrets — access is gated by each teammate's own Fellow API key at runtime.

```
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install fellow-cli

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
uv tool install fellow-cli
```

The teammate-facing install doc is one paragraph plus `fellow login`.

## Authentication

**Per-user API key, stored locally per OS-standard config dir.** Never an environment variable, never a shared workspace key.

`fellow login` flow:

1. Auto-opens `https://fellow.app/settings/api-keys` in the user's default browser.
2. Prompts for the pasted key in the terminal.
3. Validates with a `/me` (or equivalent identity) call before saving — bad key fails fast.
4. Writes to the platform config path (`~/.config/fellow/config.toml` on Linux, `~/Library/Application Support/fellow/config.toml` on macOS, `%APPDATA%\fellow\config.toml` on Windows) via `platformdirs`. File mode 600 on POSIX.

`fellow logout` deletes the stored key. `fellow me` shows the authenticated identity and workspace.

If a future teammate prefers env-var auth (CI use, etc.), the loader checks `FELLOW_API_KEY` as a fallback after the config file. Documented but not the recommended path.

## Command surface

```
fellow login | logout | me
fellow install-skill                               # optional: drop SKILL.md into ~/.claude/skills/

fellow meetings      list | get | export | open
fellow recent                                      # sugar: meetings list --since 1d
fellow transcripts   get | export
fellow summaries     get
fellow agendas       get
fellow notes         get
fellow action-items  list | get | pick             # pick = interactive TUI → JSON on stdout
fellow channels      list
fellow participants  list
```

All list commands support:
- `--since <relative-or-absolute>` — `7d`, `2026-04-01`, `2w`, etc. (single parser)
- `--channel <name-or-id>`, `--participant <email>` where applicable
- `--limit <n>` (default 50)

All `get` commands take a single resource ID.

All `export` commands take `--to <path | ->` (`-` for stdout) and `--format <json|md|both>`. When exporting multiple resources to a path, one file per resource is written; to stdout, content is concatenated.

`fellow open <meeting-id>` opens the meeting in the Fellow web UI via the default browser.

## Output format rules

| Context | Default |
|-|-|
| List commands on TTY | Pretty table |
| List commands when piped/redirected | JSON (compact) |
| `get` commands on document-y resources (transcripts, summaries, agendas, notes) | Markdown — even on TTY |
| `get` commands on metadata resources (meetings get, action-items get) | Pretty "card" on TTY, JSON when piped |
| Any command with `--json` flag | JSON, overrides defaults |

Rationale: tables don't help for transcripts; JSON doesn't help for humans skimming a list. Detect `sys.stdout.isatty()` to flip.

## Interactive picker

`fellow action-items pick` opens a TUI listing recent action items with checkboxes:

- Spacebar toggles selection
- Enter confirms — prints selected items as JSON array to stdout, exits 0
- `q` cancels — exits 1, nothing printed

Implementation: `questionary` or `prompt_toolkit` (cross-platform including Windows). No native dependencies.

The picker is the only TUI in the v1 surface. Its sole job is "select Fellow items, emit JSON." Destination (ClickUp push, etc.) is a separate tool/skill consuming stdin.

## Architecture

Python 3.10+, Click for command structure, `httpx` for the API client, `rich` for tables/markdown rendering, `platformdirs` for config paths, `questionary` for the picker. All pure-Python, no native build steps.

```
fellow_cli/
├── __main__.py             # entrypoint
├── cli.py                  # Click app, command groups
├── config.py               # config load/save, key validation
├── client.py               # FellowClient (httpx wrapper), auth, pagination, error mapping
├── commands/
│   ├── auth.py             # login, logout, me
│   ├── meetings.py
│   ├── transcripts.py
│   ├── summaries.py
│   ├── agendas.py
│   ├── notes.py
│   ├── action_items.py     # includes interactive pick
│   ├── channels.py
│   └── participants.py
├── output.py               # TTY detection, JSON vs table vs markdown rendering
└── time_parse.py           # --since parser (relative + absolute)
```

`client.py` is the single point of contact with Fellow's API. Every command goes through it. Pagination, retries (with backoff on 429/5xx), and consistent error mapping live there.

`output.py` is the single point of contact with stdout. Every command hands it a Python object and a "shape hint" (list / document / metadata); `output.py` decides table vs JSON vs markdown based on TTY + flags.

## API client behavior

- Base URL pulled from config (defaults to Fellow's documented production base).
- `X-API-KEY` header on every request.
- Automatic pagination for list endpoints — return an iterator the command layer can `--limit` against.
- Retry on 429 with `Retry-After` honored; exponential backoff on 5xx (max 3 retries).
- 401/403 produces a clear error pointing the user to `fellow login`.
- Network errors produce a clear stderr message; exit code 2.

## Caching

**v1: none.** Premature. Add later if `transcripts export` over large date ranges feels slow.

When added, cache goes to `~/.cache/fellow/` (or platform equivalent), keyed by resource ID + ETag/updated_at. Opt-in via flag at first, default-on once trusted.

## Agent discoverability

Ship a `SKILL.md` packaged with the CLI that Claude Code can discover. The skill teaches the agent: which commands exist, when to use `--json`, common pipe patterns (transcripts → `llm`, action-items pick → consumer). Installed into the user's Claude Code skills directory via `fellow install-skill` (optional one-time command).

## Testing

- Unit: every command's argument parsing + output formatter.
- Client: HTTP mocked with `respx`; pagination, retries, error mapping covered.
- E2E: a single recorded-cassette run against the real API (`vcr.py`) per command, replayed in CI. Recording requires a workspace key, kept out of CI but rerunnable locally.

## Open questions to resolve during planning

1. **Exact endpoint paths and response shapes** — confirm during planning by hitting `developers.fellow.ai/reference/*` per resource and recording cassettes.
2. **Do Fellow summaries and agendas have first-class endpoints**, or are they nested in the meetings response? If nested, drop `summaries get` / `agendas get` as top-level commands and expose via `meetings get --include summary,agenda`.
3. **Action-item assignee filter format** — email vs user ID. Affects `--assignee` parsing.
4. **Rate limits** — undocumented on the marketing site. Confirm during planning and tune retry policy.

## Out of scope, captured for later

- ClickUp / Linear / Notion push (separate tools or Claude Code skills consuming `pick` stdout).
- Write operations on action items.
- Native search (revisit when Fellow ships an endpoint).
- Watch/poll mode and webhook subscriptions.
- Homebrew tap / scoop / winget — layer on top of PyPI later if uv friction proves real.
