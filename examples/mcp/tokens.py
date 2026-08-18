"""Tabletop shell: grid, pieces, pick, turns, HUD. Rules stay in this file.

Run from the repository root:
  uv run python examples/mcp/tokens.py

Controls: click a piece, then an empty square. HUD start/restart.
Assets: KayKit knight + mage (CC0, examples/assets/kaykit).
"""

from pathlib import Path

from sceneify import Scene

# sceneify:scene-begin
def build_scene() -> Scene:
    scene = Scene("Tokens", background="#1a1410")
    scene.set_presentation(
        shadows=True,
        environmentPreset="studio",
        grid=False,
        helpers=False,
        camera={"position": [0, 12, 10], "target": [0, 0, 0], "fov": 40},
        title="Tokens",
    )
    board = scene.add_board(size=(8, 8), cell_size=1.0, title="Tokens")
    board.place(
        "token_a",
        cell=(1, 1),
        owner="P1",
        asset="kaykit-knight",
        scale=(0.42, 0.42, 0.42),
    )
    board.place(
        "token_b",
        cell=(6, 6),
        owner="P2",
        asset="kaykit-mage",
        scale=(0.42, 0.42, 0.42),
    )
    board.hud(hint="Click a piece, then an empty square.")

    @board.on_pick
    def handle(current, pick):
        if pick.kind == "piece":
            current.select(pick.node_id)
            current.highlight(current.empty_cells())
            return
        if pick.kind == "cell" and current.selected_id and pick.cell is not None:
            if pick.cell in current.highlights:
                current.move(current.selected_id, pick.cell)
                current.clear_highlights()
                current.next_turn()

    return scene
# sceneify:scene-end


if __name__ == "__main__":
    build_scene().play(project_root=Path(__file__).parents[2])
