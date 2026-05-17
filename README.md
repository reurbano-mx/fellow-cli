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

The expected usage is **inside Claude Code**: you ask Claude something, Claude runs `fellowai` for you, Claude reads the output and answers. You almost never type `fellowai` commands yourself.

Each example pairs the **English prompt you type** with the **`fellowai` command Claude runs** under the hood. If you'd rather skip Claude, type the command directly (in your terminal, or prefixed with `!` inside Claude Code).

---

### 1. Summarize this week's meetings

**You ask Claude:**

> Summarize this week's meetings — decisions made and open risks.

**Claude then runs:**

```bash
fellowai recordings export --since 7d --with-transcript --no-ai-notes \
  --format md --to /tmp/week.md
```

…reads `/tmp/week.md`, and writes the summary inline. `--no-ai-notes` is intentional — the SKILL tells Claude to summarize from the raw transcript, not Fellow's pre-generated AI notes.

**Or, automated (no Claude in the loop)** — pipe to a CLI LLM like Simon Willison's [`llm`](https://llm.datasette.io/):

```bash
fellowai recordings export --since 7d --with-transcript --no-ai-notes --format md --to - \
  | llm "summarize the key decisions and risks from these meetings"
```

---

### 2. Mark an action item complete

**You ask Claude:**

> Mark action item Qew6RGHWoe as done.

**Claude then runs:**

```bash
fellowai action-items complete Qew6RGHWoe --yes
```

Same shape for `uncomplete` and `archive`:

```bash
fellowai action-items uncomplete <id> --yes
fellowai action-items archive <id> --yes
```

---

### 3. Pick action items interactively

*(You run this one yourself — the interactive checkbox UI needs a real terminal, which Claude Code doesn't have.)*

**You run:**

```bash
fellowai action-items pick --scope mine --not-completed \
  | jq '.[] | {text, due_date}'
```

## Teaching Claude when to use this vs Fellow's MCP

Run once after login:

```bash
fellowai install-skill
```

This drops a `SKILL.md` into `~/.claude/skills/fellowai/` that Claude Code auto-discovers. It tells Claude:

- **Use Fellow's MCP** (`https://fellow.app/mcp`) for natural-language Q&A and semantic search across meetings ("what did we decide about pricing last quarter?"). That's what the MCP is built for.
- **Use this CLI** for everything else: scripted exports, write operations (complete/uncomplete/archive action items), bulk action-item workflows, piping transcripts into other tools, and anything that needs JSON output.

If you only have the CLI installed (no MCP), Claude will use the CLI for everything — it just won't have semantic search. If you have both, the skill routes Claude to the right one automatically.

**If you use multiple meeting tools** (read.ai, otter.ai, granola, etc. alongside Fellow), the skill tells Claude not to assume "the meeting" means Fellow. Be explicit when asking — say "summarize today's *Fellow* meeting" or reference a `fellow.app` link. Otherwise Claude will ask which tool to use rather than guess.

**Escape hatch — just type the command.** When you want zero ambiguity, type the literal `fellowai` invocation into the chat:

> `fellowai recordings list --since 7d --json`

Claude will run it as-is via its Bash tool. Or prefix with `!` to run it directly in your shell (output still lands in the conversation):

> `! fellowai recordings list --since 7d --json`

This bypasses the skill's routing entirely — useful when you already know the exact command and don't want to negotiate it in natural language.

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
