from click.testing import CliRunner

from fellowai.cli import cli


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "fellowai" in result.output


def test_help_lists_top_level_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in ["login", "logout", "me", "recordings", "notes", "action-items"]:
        assert cmd in result.output
