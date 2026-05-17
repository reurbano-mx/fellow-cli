# fellowai

Unofficial CLI for [Fellow.ai](https://fellow.ai)'s developer API. Designed to complement Fellow's MCP server: use the MCP to **ask questions** about meetings; use `fellowai` to **do things** with meeting data — export, automate, manage action items, pipe to LLMs.

## Install

If you don't already have `uv`, install it first:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

Then install `fellowai`:

```bash
uv tool install --prerelease=allow fellowai
```

(The `--prerelease=allow` flag is only needed while `fellowai` is on a release candidate. Drop it once `0.1.0` final ships.)

## Quick start

> **⚠️ Run `fellowai login` in a plain terminal — not inside an AI agent.**
>
> `login` is the one command where you **type your API key into a prompt**. If you run it inside Claude Code, Cursor, or any AI chat, the assistant sees your keystrokes. Do it once in a regular terminal. Every other `fellowai` command is safe inside an AI agent — the key is read from your 0o600 config file and sent only in the `X-API-KEY` HTTP header (never in URLs, output, or tracebacks).

```bash
fellowai login        # prompts for workspace subdomain and API key (plain terminal!)
fellowai me           # confirms you're authenticated
fellowai recordings list --since 7d
```

To create an API key: in Fellow, click your workspace name (top left) → **User Settings → API, MCP & Webhooks → New API key**. Your workspace admin may need to enable Developer API access under **Workspace Settings → Security** first.

`fellowai login` prints the workspace URL but does not auto-open your browser. Pass `--open-browser` if you want it to.

You can also set `FELLOWAI_SUBDOMAIN` and `FELLOWAI_API_KEY` as environment variables (both required together) to bypass the config file — useful for CI.

## Three sample pipelines

**1. Summarize this week's meetings — inside Claude Code (or any AI agent)**

Just ask:

> "Use fellowai to export this week's meeting transcripts to /tmp/week.md, then summarize the key decisions and risks."

The agent will run `fellowai recordings export --since 7d --with-transcript --format md --to /tmp/week.md`, read the file, and summarize. No extra tools needed.

For unattended automation (cron, scripts), pipe to a CLI LLM like Simon Willison's [`llm`](https://llm.datasette.io/):

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

## Global flags

| Flag | What it does |
|-|-|
| `--debug` | Print full tracebacks on errors instead of one-line messages |
| `--verbose` / `-v` | Log every HTTP request and response to stderr (e.g. `→ POST .../recordings`, `← 200 ... (1632 bytes)`) |
| `--version` | Show version and exit |

## Security

- Your API key is stored at the platform's user config dir (`~/Library/Application Support/fellowai/config.toml` on macOS, `$XDG_CONFIG_HOME/fellowai/` on Linux) with file mode `0o600` and the parent dir at `0o700`. The config dir is created and hardened race-free using fd-relative operations on POSIX; a foreign-owned or symlinked dir is refused with an error.
- Resource ids are validated against `^[A-Za-z0-9_-]{1,64}$` before URL interpolation, so `fellowai recordings get '../me'` cannot be tricked into hitting a different endpoint.
- All API traffic uses TLS; the key is sent only in the `X-API-KEY` header, never in URLs.

## Status

v0.x — pre-1.0, breaking changes possible at minor bumps. Pin via `uv tool install 'fellowai==0.1.*'` if needed.
