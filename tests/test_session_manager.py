"""Tests for isolated MCP example session templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from sceneify.session_manager import SessionManager


def test_create_example_world_uses_run(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    path = manager.create_example("demo-world")
    text = path.read_text(encoding="utf-8")
    assert "# sceneify:scene-begin" in text
    assert "# sceneify:scene-end" in text
    assert "ExperienceManifest.present" in text
    assert ".run(" in text
    assert ".play(" not in text


def test_create_example_game_uses_play_and_markers(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    path = manager.create_example("demo-game", kind="game", title="Ruins")
    text = path.read_text(encoding="utf-8")
    assert "# sceneify:scene-begin" in text
    assert "# sceneify:scene-end" in text
    assert "scene.character" in text
    assert "play.objective" in text
    assert "scene.play(" in text or ".play(" in text
    assert ".run(" not in text


def test_create_example_rejects_unknown_kind(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    with pytest.raises(ValueError, match="world"):
        manager.create_example("bad", kind="chess")


def test_scaffold_present_character_and_board(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    present = manager.scaffold("present", name="hall", title="Hall")
    text = present.read_text(encoding="utf-8")
    assert "ExperienceManifest.present" in text
    assert "export_web" in text
    assert "<sceneify-viewer>" in text or "EMBED.txt" in text
    assert ".run(" in text

    character = manager.scaffold("character", name="dungeon", title="Ruins")
    body = character.read_text(encoding="utf-8")
    assert "scene.character" in body
    assert "play.objective" in body
    assert ".play(" in body

    board = manager.scaffold("board", name="table", title="Tokens")
    rules = board.read_text(encoding="utf-8")
    assert "add_board" in rules
    assert "@board.on_pick" in rules
    assert "kaykit-knight" in rules
    assert "kaykit-mage" in rules
    assert "chess" not in rules.lower()
    assert ".play(" in rules

    with pytest.raises(ValueError, match="family"):
        manager.scaffold("chess")
