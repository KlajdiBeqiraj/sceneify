"""Tests for the bundled Agent Skill installer."""

from __future__ import annotations

from pathlib import Path

import pytest

from sceneify.cli import main
from sceneify.skills import SKILL_NAME, bundled_skill_dir, install_skill, open_bundled_skill_dir


def test_bundled_skill_contains_skill_md() -> None:
    with open_bundled_skill_dir() as path:
        skill = path / "SKILL.md"
        assert skill.is_file()
        text = skill.read_text(encoding="utf-8")
        assert "name: sceneify-mcp" in text
        assert "sceneify_apply" in text
        assert "scene.play()" in text
        assert "scene.run()" in text
        assert "on_input" in text
        assert "on_tick" in text
        assert "Do not use annotations as match HUD" in text
        assert "packed to `.glb`" in text
        assert "sceneify_scaffold" in text
        assert "family=present" in text or "present | character | board" in text or "`present`" in text
        assert "<sceneify-viewer>" in text
        assert "add_board" in text
        assert "Do not use annotations as match HUD" in text
        assert "Do **not** send `extra`" in text


def test_install_skill_default_agents_target(tmp_path: Path) -> None:
    installed = install_skill(base_dir=tmp_path)
    assert len(installed) == 1
    skill = installed[0]
    assert skill == tmp_path / ".agents" / "skills" / SKILL_NAME
    assert (skill / "SKILL.md").is_file()


def test_install_skill_all_targets(tmp_path: Path) -> None:
    installed = install_skill(target="all", base_dir=tmp_path)
    assert len(installed) == 4
    for path in installed:
        assert (path / "SKILL.md").is_file()


def test_install_skill_refuses_overwrite_without_force(tmp_path: Path) -> None:
    install_skill(base_dir=tmp_path)
    with pytest.raises(FileExistsError):
        install_skill(base_dir=tmp_path)
    install_skill(base_dir=tmp_path, force=True)


def test_cli_install_skill(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["install-skill", "--dir", str(tmp_path)])
    out = Path(capsys.readouterr().out.strip())
    assert out == tmp_path.resolve() / ".agents" / "skills" / SKILL_NAME
    assert (out / "SKILL.md").is_file()


def test_cli_skill_path(capsys: pytest.CaptureFixture[str]) -> None:
    main(["skill-path"])
    out = Path(capsys.readouterr().out.strip())
    assert out.is_dir()
    assert (out / "SKILL.md").is_file()
    # Prefer the stable repo path when running from a source checkout.
    assert out == bundled_skill_dir() or out.name == SKILL_NAME
