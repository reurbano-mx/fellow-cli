"""Action-items commands: list, get, complete, uncomplete, archive."""

from __future__ import annotations

import sys
from typing import Any

import click

from fellowai.client import FellowError
from fellowai.commands import make_client as _client
from fellowai.output import emit, render_action_item_card
from fellowai.time_parse import parse_since


_SCOPE_MAP = {"mine": "assigned_to_me", "others": "assigned_to_others", "all": "all"}
_ORDER_MAP = {"newest": "created_at_desc", "oldest": "created_at_asc", "due": "due_date"}


def _build_filters(scope: str, completed: bool | None,
                   archived: bool | None, ai_detected: bool | None,
                   ai_suggestion_accepted: bool | None = None) -> dict:
    filters: dict[str, Any] = {"scope": _SCOPE_MAP[scope]}
    if completed is not None:
        filters["completed"] = completed
    if archived is not None:
        filters["archived"] = archived
    if ai_detected is not None:
        filters["ai_detected"] = ai_detected
    if ai_suggestion_accepted is not None:
        filters["ai_suggestion_accepted_by_user"] = ai_suggestion_accepted
    return filters


@click.command(name="list")
@click.option("--scope", type=click.Choice(["mine", "others", "all"]), default="mine")
@click.option("--completed/--not-completed", "completed", default=None)
@click.option("--archived/--not-archived", "archived", default=None)
@click.option("--ai-detected/--not-ai-detected", "ai_detected", default=None)
@click.option("--ai-suggestion-accepted/--ai-suggestion-not-accepted",
              "ai_suggestion_accepted", default=None)
@click.option("--order", "order", type=click.Choice(["newest", "oldest", "due"]), default=None)
@click.option("--since", help="Filter client-side on created_at (no server-side filter)")
@click.option("--limit", type=int, default=50)
@click.option("--page-size", type=click.IntRange(1, 50), default=20)
@click.option("--json", "format_override", flag_value="json")
def ai_list(scope, completed, archived, ai_detected, ai_suggestion_accepted,
            order, since, limit, page_size, format_override):
    """List action items."""
    client = _client()
    try:
        filters = _build_filters(scope, completed, archived, ai_detected, ai_suggestion_accepted)
        order_by = _ORDER_MAP[order] if order else None
        items = list(client.list_action_items(
            filters=filters, order_by=order_by, limit=limit, page_size=page_size,
        ))
        if since:
            cutoff = parse_since(since)
            items = [i for i in items if (i.get("created_at") or "") >= cutoff]
    except (FellowError, ValueError) as e:
        from fellowai.errors import handle
        handle(e)

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
    except (FellowError, ValueError) as e:
        from fellowai.errors import handle
        handle(e)
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
    except (FellowError, ValueError) as e:
        from fellowai.errors import handle
        handle(e)
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
    except (FellowError, ValueError) as e:
        from fellowai.errors import handle
        handle(e)
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
    except (FellowError, ValueError) as e:
        from fellowai.errors import handle
        handle(e)
    if format_override == "json":
        emit(item, shape="card", format_override="json")
    else:
        click.echo(f"✓ Archived: {item.get('text', action_item_id)}")


def _is_tty() -> bool:
    return sys.stdin.isatty()


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
    if not _is_tty():
        click.echo(
            "Action item picker requires a terminal. Run interactively, "
            "or use 'action-items list --json' to get JSON without selection.",
            err=True,
        )
        sys.exit(1)

    client = _client()
    try:
        filters = _build_filters(scope, completed, archived, ai_detected)
        items = list(client.list_action_items(filters=filters, limit=limit, page_size=page_size))
    except (FellowError, ValueError) as e:
        from fellowai.errors import handle
        handle(e)

    if not items:
        click.echo("No action items to pick from.", err=True)
        sys.exit(1)

    selected = _prompt_selection(items)
    if not selected:
        sys.exit(1)

    emit(selected, shape="list", columns=["id", "text"], format_override="json")


def register(group: click.Group) -> None:
    group.add_command(ai_list)
    group.add_command(ai_get)
    group.add_command(ai_pick)
    group.add_command(ai_complete)
    group.add_command(ai_uncomplete)
    group.add_command(ai_archive)
