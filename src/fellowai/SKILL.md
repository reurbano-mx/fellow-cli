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
