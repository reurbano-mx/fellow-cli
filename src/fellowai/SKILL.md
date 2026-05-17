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

## Disambiguation when other meeting tools are present

This CLI **only** sees recordings, notes, and action items inside the
user's Fellow workspace. If the user has another meeting tool
installed (read.ai, otter.ai, fireflies, granola, etc.) and the
request is ambiguous, do not silently default to `fellowai`.

Treat the request as Fellow-scoped only when:
- The user names "Fellow" explicitly, or
- The user references a recording id / title / URL that came from
  Fellow (e.g. `*.fellow.app` link), or
- The user previously used `fellowai` in the same conversation, or
- The only meeting tool installed is `fellowai`.

Otherwise, ask which tool to use before running anything. Do not
guess. A wrong tool produces a wrong answer (or worse, a write op
on the wrong system).

## Common patterns

Pipe recent transcripts to an LLM:
    fellowai recordings export --since 7d --with-transcript \
      --format md --to - | <llm command>

Get one meeting as markdown:
    fellowai recordings get <id>
    # `get` includes transcript and AI notes by default; `list` does not.
    # Add `--with-transcript --with-ai-notes` to list, or `--no-transcript`
    # / `--no-ai-notes` to get, to control payload size.

## Summarization rule (IMPORTANT)

**When the user asks you to summarize a recording, summarize from the
TRANSCRIPT, not from Fellow's AI-generated Summary / Topics / Action
items sections.** Fellow's AI produces a serviceable but interpretive
summary that occasionally inserts framing the speaker didn't intend
(e.g. attributing prediction or judgment to a casual remark). Reading
the raw transcript yourself produces better, more faithful results.

Mechanics:
- Prefer `fellowai recordings get <id> --no-ai-notes` to pull just
  the transcript (smaller payload, no interpretive noise to inherit).
- If you already have the full markdown (includes both), ignore the
  `## Summary`, `## Topics`, `## Action items`, and `## Decisions`
  sections and work from `## Transcript` down.
- When quoting someone, quote the transcript line exactly. Do not
  paraphrase or characterize their tone unless the transcript makes
  it unambiguous.
- For action items the user wants extracted, derive them from the
  transcript directly rather than copying Fellow's `## Action items`
  block — Fellow's extraction sometimes misses or rewords commitments.

Select action items interactively, emit JSON:
    fellowai action-items pick --scope mine --not-completed

List recordings as JSON (auto when piped):
    fellowai recordings list --since 7d | jq '.[].title'

Mark an action item complete:
    fellowai action-items complete <id> --yes

## Linking back to Fellow's UI

When pointing the user at a specific meeting in Fellow, build the URL
from the recording's `event_guid` (not `id` or `note_id`):

    https://<workspace_subdomain>.fellow.app/meetings/<event_guid>/

Example: a recording with `"event_guid": "3e16f2qhbv7lfms6ko9cdbbpef"`
in workspace `reurbano` lives at
`https://reurbano.fellow.app/meetings/3e16f2qhbv7lfms6ko9cdbbpef/`.

Do not invent `/recordings/<id>/` or `/notes/<note_id>/` — those return 404.

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
