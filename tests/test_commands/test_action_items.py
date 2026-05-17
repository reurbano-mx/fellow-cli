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


def test_pick_emits_selected_as_json(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    items = [
        {"id": "a", "text": "First", "status": "Incomplete"},
        {"id": "b", "text": "Second", "status": "Incomplete"},
        {"id": "c", "text": "Third", "status": "Incomplete"},
    ]
    with patch("fellowai.commands.action_items.FellowClient") as MockClient, \
         patch("fellowai.commands.action_items._prompt_selection") as MockPrompt, \
         patch("fellowai.commands.action_items._is_tty", return_value=True):
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
         patch("fellowai.commands.action_items._prompt_selection") as MockPrompt, \
         patch("fellowai.commands.action_items._is_tty", return_value=True):
        MockClient.return_value.list_action_items.return_value = iter(items)
        MockPrompt.return_value = None  # user pressed q / Ctrl-C
        result = runner.invoke(cli, ["action-items", "pick"])
    assert result.exit_code == 1


def test_pick_without_tty_exits_with_sentence_error(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    runner = CliRunner()
    with patch("fellowai.commands.action_items._is_tty", return_value=False):
        result = runner.invoke(cli, ["action-items", "pick"])
    assert result.exit_code == 1
    assert "requires a terminal" in result.output
