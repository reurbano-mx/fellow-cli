from pathlib import Path

import pytest
from click.testing import CliRunner

from fellowai.cli import cli


def test_install_skill_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["install-skill"])
    assert result.exit_code == 0
    skill_file = tmp_path / ".claude" / "skills" / "fellowai" / "SKILL.md"
    assert skill_file.exists()
    content = skill_file.read_text()
    assert "fellowai" in content
    assert "fellowai recordings export" in content
