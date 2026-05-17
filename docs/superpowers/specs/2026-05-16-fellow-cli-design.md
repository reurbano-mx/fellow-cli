# fellowai — Design Spec

**Date:** 2026-05-16 (updated after Playwright API recon)
**Status:** Draft for review
**Owner:** Kramer Sharp (primary users: Kramer + Chris, possibly half of Reurbano)
**Command name:** `fellowai`

## Problem

Reurbano uses Fellow.ai for meeting recordings, transcripts, and action items. The official Fellow MCP server (hosted at `https://fellow.app/mcp`) is available but has two problems:

1. **Context tax.** MCP tool definitions stay loaded every turn. A permanent token cost on every Claude Code session, whether or not Fellow is used.
2. **Surface limits.** The MCP exposes a fixed read-only shape; we can't compose its outputs cleanly with Unix pipes, can't batch-export, can't drive an interactive picker, can't trigger write operations.

A CLI fixes both. It costs zero permanent context (the agent reads `--help` only when needed), it composes with standard tools, and we control the surface.

## Relationship to the Fellow MCP

The CLI does **not** replace the MCP. They serve different jobs and are intended to coexist.

**The Fellow MCP (5 read-only tools): `get_action_items`, `get_meeting_participants`, `get_meeting_summary`, `get_meeting_transcript`, `search_meetings`.**

**Use the MCP when you want to:**
- Ask natural-language questions about meetings ("what did we decide about the launch date?", "summarize feedback I gave Jake last month").
- Do **semantic search across meetings** — this is the MCP's killer feature; the public REST API has no equivalent search endpoint.
- Work inside a conversational AI client (Claude Desktop, ChatGPT, Cursor) without building anything.

**Use this CLI when you want to:**
- Pipe Fellow data through Unix tools (`recordings export --include transcript --to - | llm "..."`, into `jq`, `rg`, scripts).
- Drive the **action-items picker → ClickUp** pipeline (and similar future pipelines).
- Trigger **write operations** the MCP can't: mark action items complete, archive them.
- Download the actual **audio/video media file** (`media_url`, requires a privileged API key).
- Pull data into **cron jobs / scripts / non-Claude LLMs / automation** outside an MCP-aware chat client.
- Avoid the always-on MCP context tax during sessions that don't touch Fellow at all.

**Positioning in docs and SKILL.md:** "Use the MCP when you want to ask questions about your meetings. Use `fellowai` when you want to *do things* with meeting data — export, automate, complete action items, build pipelines."

**One capability we explicitly do not replicate:** semantic search. Faking it client-side (export-everything-then-grep) is a bad lie. If you need search, use the MCP for that one query.

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

Endpoint list confirmed via Playwright crawl of `developers.fellow.ai/reference/*`; resource shapes confirmed by direct probes against `reurbano.fellow.app` on 2026-05-16:

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
| Action Items | Mark complete | POST | `/action_item/{id}/complete` |
| Action Items | Archive | POST | `/action_item/{id}/archive` |
| Webhooks | Create/Retrieve/Update/Delete/List | POST/GET/PATCH/DELETE/GET | — |

### Resource shapes (verified)

**`/me`** → `{ user: {id, email, full_name}, workspace: {id, name, subdomain} }`

**Recording**:
- Always: `id, title, created_at, updated_at, started_at, ended_at, event_call_url, event_guid, note_id, user_has_calendar_event`
- Optional (always present as keys but **null** unless requested):
  - `transcript: { speech_segments: [{start, end, speaker, text}], language_code }` — **inline, not a sub-URL**
  - `ai_notes: [{ id, is_active, title, template_creator, sections: [{title, type, content}] }]` — array of templates; section types `STANDARD`/`CUSTOM`; section content can be a string (Summary), or arrays for `Action items` / `Decisions` / `Topics` / `Key Moments`
  - `media_url: string | null` — pre-signed URL for audio/video

**Critical asymmetry between list and get:**

- `POST /recordings` (list) — `transcript` and `ai_notes` are `null` unless `include.transcript=true` / `include.ai_notes=true`. Default list calls are cheap.
- `GET /recording/{id}` (single) — **`transcript` and `ai_notes` are populated by default**, no include needed. So `fellowai recordings get <id>` returns everything; `fellowai recordings list` requires opt-in.

**Note**:
- Always: `id, created_at, updated_at, title, event_guid, event_start, event_end, event_is_all_day, recording_ids[]`
- Optional (include keys are `event_attendees` and `content_markdown`):
  - `event_attendees: [{email}] | null`
  - `content_markdown: string | null` (the human-edited markdown body of the note)

`recording_ids` is **plural** — a single Note can correspond to multiple Recordings (recurring meetings).

`GET /note/{id}` returns event_attendees + content_markdown populated by default; `POST /notes` (list) requires opt-in. Same asymmetry as Recordings.

**ActionItem**:
- `id, text, status, created_at, updated_at, due_date, note_id, assignees, completion_type, ai_detected, recording_offset, ai_suggestion_accepted_by_user`
- `status` is a **string**: `"Incomplete"` or `"Complete"` (for display)
- `assignees` is an **array**: `[{id, full_name, email}, ...]`
- `recording_offset` is seconds into the source recording where the item was extracted (enables future "jump to moment" feature)
- **Asymmetry**: the *filter* uses `completed: boolean`, but the *response* uses `status: string`. The client maps between them.

### media_url behavior — corrected from earlier draft

Probing `include.media_url=true` with a non-privileged key returned **`media_url: null` with HTTP 200**, not a 403. This changes the error UX: instead of a forbidden-error sentence, we detect `null` when the user passed `--with-media` and emit a sentence-shaped warning to stderr:

```
Warning: media_url was requested but is null. This usually means your API
key is not privileged. Ask a workspace admin for a privileged key to
download recording audio/video.
```

The command still succeeds (exit 0) and emits the other data; the warning is just an explainer.

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
fellowai action-items list | get | pick | complete | uncomplete | archive
```

Common pagination flags:

- `--limit <n>` — total records returned to the user (default 50). The client paginates underneath; user never sees pages.
- `--page-size <n>` — API page size (1–50, default 20). Tune only for very large `--limit`s.

### `recordings list/get/export`

Filter flags on `list` and `export` (mapped to confirmed API filter fields):

- `--since <relative-or-absolute>` → `created_at_start` (e.g., `7d`, `2026-04-01`)
- `--until <relative-or-absolute>` → `created_at_end`
- `--updated-since` → `updated_at_start` (when you want recordings whose notes/transcript were edited recently)
- `--channel <id>` → `channel_id`
- `--title <substring>` → `title`
- `--event <guid>` → `event_guid` (filter by calendar event)

Include flags on `list` and `export` (control expensive nested fields, default off):

- `--with-transcript` → `include.transcript = true` (inline `speech_segments`)
- `--with-ai-notes` → `include.ai_notes = true` (Summary, Action items, Decisions, Topics, Key Moments)
- `--with-media` → `include.media_url = true`. Returns `null` for non-privileged keys (no error); the CLI emits a stderr warning explaining this when null is observed.

**`recordings get <id>` does not need `--with-*` flags** — the API returns `transcript`, `ai_notes`, and `media_url` populated by default on the single-resource GET. `--no-transcript` / `--no-ai-notes` / `--no-media` are available to suppress them client-side for compact output.

### `notes list/get/export`

Filter flags (Notes accepts the same `created_at_start` filter as Recordings — verified):

- `--since` → `created_at_start`
- `--until` → `created_at_end`
- (other filters like `--updated-since`, `--title`, `--channel`, `--event` available pending confirmation that Notes uses the same RecordingFilters schema; if not, those flags are omitted in v1)

Include flags (verified):

- `--with-content` → `include.content_markdown = true` (the human-edited markdown body)
- `--with-attendees` → `include.event_attendees = true`

As with Recordings, `notes get <id>` returns these fields populated by default; the include flags only matter for `list` / `export`.

### `action-items list/get/pick/complete/uncomplete/archive`

Confirmed filter flags (server-side):

- `--scope <mine|others|all>` → `scope: assigned_to_me | assigned_to_others | all` (default `mine`)
- `--completed / --not-completed` → `completed: true|false`
- `--archived / --not-archived` → `archived: true|false`
- `--ai-detected / --not-ai-detected` → `ai_detected: true|false`
- `--order <newest|oldest|due>` → `order_by: created_at_desc | created_at_asc | due_date`

Client-side filter (no server-side equivalent):

- `--since <relative-or-absolute>` filters the returned page on `created_at` after fetching. Documented limitation: paginates the full set until enough matches are found. Worth flagging to the user; if Fellow ships a date filter later, switch to server-side.

Write commands:

- `complete <id>` → `POST /action_item/{id}/complete` with `{ "completed": true }`
- `uncomplete <id>` → same endpoint with `{ "completed": false }` (the API endpoint is a toggle; exposing two commands is clearer than `complete --undo`)
- `archive <id>` → `POST /action_item/{id}/archive` (no body)
- Both prompt for confirmation by default; `--yes` skips. `--json` prints the updated item.

### `pick` — interactive TUI

`fellowai action-items pick` accepts the same filter flags as `list`, opens a TUI with checkboxes:

- Spacebar toggles selection, arrows navigate, `/` filters by substring
- Enter confirms — prints selected items as JSON array to stdout, exits 0
- `q` cancels — exits 1, nothing printed
- Implementation: `questionary` (cross-platform, no native deps)

### `export` for recordings and notes

- `--to <path | ->` — writes to a directory (one file per resource: `<id>.<ext>`) or stdout (`-`)
- `--format <json|md|both>` — for `--to <path>`: `both` writes `<id>.json` + `<id>.md` per resource. For `--to -`: `both` is rejected (concatenation ambiguous).
- Markdown rendering for a Recording: title + dates + `transcript` (if included) as `[speaker]: text` lines + `ai_notes` rendered with section headers.

## Sample session

```
$ fellowai login
Workspace subdomain: reurbano
Opening https://reurbano.fellow.app/settings/api-keys...
API key: ********************************
✓ Authenticated as kramer@reurbano.mx
✓ Saved to ~/.config/fellowai/config.toml

$ fellowai me
kramer@reurbano.mx  workspace: reurbano  key: ...d7f3 (last 4)

$ fellowai recordings list --since 7d
ID         TITLE                       STARTED              DURATION
rec_abc12  Q2 planning                 2026-05-13 09:00     58m
rec_def34  1:1 with Chris              2026-05-14 14:30     32m
rec_ghi56  Vendor renewal call         2026-05-15 11:00     47m

$ fellowai recordings export --since 7d --with-transcript --format md --to - | \
    llm "summarize key decisions and risks from these meetings"

$ fellowai action-items pick --scope mine --not-completed | \
    jq '.[] | {title, due_date}'

$ fellowai action-items complete ai_xyz789 --yes
✓ Marked complete: "Email vendor about renewal"
```

## Acceptance criteria — v1 ships when

1. `fellowai login` / `me` / `logout` work end-to-end against the live API, persisting + reading config across platforms (macOS verified manually, Linux + Windows verified via CI smoke).
2. `recordings list` / `get` / `export` work with all filter flags above and both `--with-*` include modes (excluding `--with-media`, which needs a privileged key to fully verify).
3. `notes list` / `get` / `export` work; filter set confirmed against live API.
4. `action-items list` / `get` / `pick` / `complete` / `uncomplete` / `archive` work end-to-end; `pick` produces composable JSON.
5. Error UX: all auth/network/rate-limit/bad-ID failures produce sentence-shaped errors, never tracebacks (verified via `respx` mocked tests).
6. Empty results produce `[]` on stdout when piped, friendly sentence on TTY.
7. SKILL.md installs to `~/.claude/skills/fellowai/` via `fellowai install-skill` and Claude Code can discover the skill.
8. Published to PyPI as `fellowai`; `uv tool install fellowai` works on macOS / Linux / Windows.
9. README has the install/login walkthrough plus three sample pipelines from the Sample Session block.

## Edge-case behaviors

- **Empty results.** Exit 0 in all cases. On TTY: `No recordings in the last 7 days.` When piped: `[]` (or empty markdown). Never a non-zero exit on "nothing to show."
- **Mid-session 401.** Any API call returning 401 prints the sentence error and exits 2. Never a stack trace. Config is *not* auto-deleted (the user might be on a stale subdomain) — we just point them at `fellowai login`.
- **Rate limit (429).** Honor `Retry-After` if present; otherwise back off `1s, 2s, 4s` (max 3 retries). After exhaustion, sentence error with the documented per-key limits (3/sec, 10,000/day).
- **API surface drift.** The client uses Pydantic models with `extra="allow"` so new server fields don't break us. Missing required fields produce a clear `Fellow API returned an unexpected response — run with --debug for details.`
- **`--limit` vs `--page-size`.** `--limit` is the user contract; `--page-size` is an implementation tuning knob. Default `--page-size 20` matches the API default; users almost never need to set it.

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

A `SKILL.md` ships inside the package. `fellowai install-skill` copies it into `~/.claude/skills/fellowai/`. Draft body:

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
    fellowai recordings get <id> --with-ai-notes --md

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
- 403 on `--with-media` → privileged API key required; ask a workspace
  admin
- 429 → wait; rate limits are 3/sec, 10,000/day per key
- Empty result is exit 0, not an error

## What this CLI can't do

- Search meetings (use the MCP)
- List channels or participants (no REST endpoint)
- Webhook management (deferred in v1)
- Delete recordings/notes (deferred in v1)
```

## Open questions to resolve during implementation

Most prior unknowns are now answered by direct probes. Remaining:

1. Full filter set for Notes beyond `created_at_start` (Recordings has `updated_at_*`, `channel_id`, `title`, `event_guid` — confirm Notes accepts the same set by probing at implementation time).
2. Whether there's a `MediaUrlConfig` expiration parameter (probed with `include.media_url=true` only; the documented `media_url: MediaUrlConfig` top-level body field may give finer control).
3. Rate-limit response body shape — only the documented spec (HTTP 429 + `rate_limited` code) is confirmed; want to capture the exact error JSON when implementing the retry layer.

## Out of scope, captured for later

- Recording/note deletion (`DELETE` endpoints exist).
- Webhook management (full Create/Retrieve/Update/Delete/List surface exists).
- Watch/poll mode.
- ClickUp / Linear / Notion push (separate tools or skills consuming `pick` stdout).
- Caching layer.
- Homebrew tap / scoop / winget — layer on top of PyPI later if `uv tool install` friction proves real.
- Generating SKILL.md from `--help` at install time.
