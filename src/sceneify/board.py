"""Streamlit-like tabletop board DSL.

The runtime owns cells, pick events, highlights, turns, and HUD chrome.
Python owns legality, move effects, and win conditions — a few lines, not an engine.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from sceneify.catalog import AssetCatalog
from sceneify.experience import ExperienceManifest, TabletopPiece
from sceneify.objects import Material, Physics
from sceneify.realtime import SemanticEvent

if TYPE_CHECKING:
    from sceneify.scene import Scene

BoardOutcome = Literal["win", "lose", "draw"]
PickKind = Literal["piece", "cell", "other"]
PickCallback = Callable[["Board", "BoardPick"], Any]


@dataclass(frozen=True, slots=True)
class BoardPick:
    """A play-mode click resolved onto a cell or piece."""

    node_id: str
    kind: PickKind
    cell: tuple[int, int] | None = None


class Board:
    """Grid + pieces + pick/turn HUD attached to a scene."""

    def __init__(
        self,
        scene: Scene,
        *,
        rows: int,
        cols: int,
        cell_size: float = 1.0,
        origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
        title: str | None = None,
        owners: list[str] | None = None,
        light: str = "#cfc6b8",
        dark: str = "#6d5c4d",
    ) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("Board size must be at least 1x1")
        if cell_size <= 0:
            raise ValueError("cell_size must be greater than zero")
        self.scene = scene
        self.rows = rows
        self.cols = cols
        self.cell_size = float(cell_size)
        self.origin = (float(origin[0]), float(origin[1]), float(origin[2]))
        self.light = light
        self.dark = dark
        self._on_pick: PickCallback | None = None
        self._pieces: dict[str, TabletopPiece] = {}
        experience = ExperienceManifest.board(
            rows=rows,
            cols=cols,
            cell_size=cell_size,
            origin=self.origin,
            title=title,
            owners=owners,
        )
        scene.set_experience(experience)
        self._build_cells()
        scene.on_event(self._handle_event)

    @property
    def selected_id(self) -> str | None:
        tabletop = self._tabletop()
        return None if tabletop is None else tabletop.selected_id

    @property
    def turn(self) -> int:
        tabletop = self._tabletop()
        return 0 if tabletop is None else tabletop.turn

    @property
    def highlights(self) -> list[tuple[int, int]]:
        cells: list[tuple[int, int]] = []
        for node_id in self._tabletop_highlights():
            cell = self.cell_of(node_id)
            if cell is not None:
                cells.append(cell)
        return cells

    def hud(self, **options: Any) -> None:
        """Configure match HUD title, hint, and outcome messages."""
        manifest = self._manifest()
        if "title" in options:
            manifest.hud.title = options["title"]
        if "hint" in options or "controls_hint" in options:
            manifest.hud.hint = options.get("hint") or options.get("controls_hint")
        if "description" in options:
            manifest.hud.description = options["description"]
        if "win_message" in options:
            manifest.hud.win_message = options["win_message"]
        if "lose_message" in options:
            manifest.hud.lose_message = options["lose_message"]
        if "draw_message" in options:
            manifest.hud.draw_message = options["draw_message"]
        self._commit(manifest)

    def place(
        self,
        piece_id: str,
        *,
        cell: tuple[int, int] | list[int],
        owner: str | None = None,
        primitive: str = "cylinder",
        color: str = "#e8e0d4",
        asset: str | None = None,
        source: str | Path | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        """Spawn a piece on a cell.

        Pass ``asset`` (catalog id) or ``source`` (GLB path) for a mesh piece.
        Otherwise ``primitive`` may be box, sphere, capsule, or cylinder.
        """
        coord = self._cell(cell)
        if self.piece_at(coord) is not None:
            raise ValueError(f"Cell {coord} is already occupied")
        physics = options.pop("physics", Physics(body="kinematic", collider="cuboid", sensor=True))
        tags = ["board-piece", *(options.pop("tags", []) or [])]
        if asset is not None or source is not None:
            path, catalog_id = _resolve_piece_mesh(asset, source)
            position = self.cell_position(coord, y=self.origin[1] + 0.04)
            extra: dict[str, Any] = {}
            if catalog_id:
                extra["catalog_asset"] = catalog_id
            node = self.scene.add_glb(
                piece_id,
                path,
                position=position,
                rotation=options.pop("rotation", None),
                scale=options.pop("scale", (1.0, 1.0, 1.0)),
                apply_environment=False,
                physics=physics,
                tags=tags,
                **extra,
                **options,
            )
        else:
            position = self.cell_position(coord, y=self.origin[1] + 0.28)
            shape = "capsule" if primitive == "cylinder" else primitive
            node = self.scene.create_primitive(
                piece_id,
                shape,
                position=position,
                radius=float(options.pop("radius", self.cell_size * 0.28)),
                height=float(options.pop("height", 0.36)),
                size=options.pop("size", (self.cell_size * 0.55, 0.28, self.cell_size * 0.55)),
                material=options.pop("material", Material(color)),
                physics=physics,
                tags=tags,
                **options,
            )
        node.meta["cell"] = [coord[0], coord[1]]
        node.meta["boardRole"] = "piece"
        if owner:
            node.meta["owner"] = owner
        piece = TabletopPiece(id=piece_id, cell=coord, owner=owner)
        self._pieces[piece_id] = piece
        manifest = self._manifest()
        assert manifest.tabletop is not None
        manifest.tabletop.pieces = [item for item in manifest.tabletop.pieces if item.id != piece_id]
        manifest.tabletop.pieces.append(piece)
        self._commit(manifest)
        return node.to_dict()

    def on_pick(self, callback: PickCallback | None = None) -> PickCallback | Callable:
        """Register ``callback(board, pick)`` for play-mode clicks."""

        def register(candidate: PickCallback) -> PickCallback:
            if not callable(candidate):
                raise TypeError("Board on_pick callback must be callable")
            self._on_pick = candidate
            return candidate

        return register(callback) if callback is not None else register

    def select(self, piece_id: str | None) -> None:
        manifest = self._manifest()
        assert manifest.tabletop is not None
        manifest.tabletop.selected_id = piece_id
        self._commit(manifest)

    def highlight(self, cells: list[tuple[int, int] | list[int]] | tuple[int, int]) -> None:
        coords = cells if isinstance(cells, list) else [cells]
        ids = [self.cell_id(self._cell(cell)) for cell in coords]
        manifest = self._manifest()
        assert manifest.tabletop is not None
        manifest.tabletop.highlights = ids
        self._commit(manifest)

    def clear_highlights(self) -> None:
        self.highlight([])

    def next_turn(self) -> int:
        manifest = self._manifest()
        assert manifest.tabletop is not None
        count = max(1, manifest.tabletop.turn_count)
        manifest.tabletop.turn = (manifest.tabletop.turn + 1) % count
        manifest.tabletop.selected_id = None
        self._commit(manifest)
        return manifest.tabletop.turn

    def end(self, outcome: BoardOutcome, message: str | None = None) -> None:
        if outcome not in {"win", "lose", "draw"}:
            raise ValueError("Board outcome must be win, lose, or draw")
        manifest = self._manifest()
        phase: Literal["won", "lost", "draw"] = {
            "win": "won",
            "lose": "lost",
            "draw": "draw",
        }[outcome]  # type: ignore[assignment]
        manifest.match.phase = phase
        if message:
            if outcome == "win":
                manifest.hud.win_message = message
            elif outcome == "lose":
                manifest.hud.lose_message = message
            else:
                manifest.hud.draw_message = message
        manifest.tabletop.selected_id = None if manifest.tabletop else None
        self._commit(manifest)

    def move(self, piece_id: str, cell: tuple[int, int] | list[int]) -> None:
        coord = self._cell(cell)
        occupant = self.piece_at(coord)
        if occupant is not None and occupant != piece_id:
            raise ValueError(f"Cell {coord} is occupied by {occupant}")
        node = self.scene._graph_nodes().get(piece_id)
        if node is None:
            raise KeyError(f"Unknown piece id {piece_id!r}")
        current_y = float(node.position[1]) if node.position else self.origin[1] + 0.28
        position = self.cell_position(coord, y=current_y)
        self.scene.patch_node(piece_id, {"position": list(position)})
        node.meta["cell"] = [coord[0], coord[1]]
        piece = self._pieces.get(piece_id) or TabletopPiece(id=piece_id, cell=coord)
        piece.cell = coord
        self._pieces[piece_id] = piece
        manifest = self._manifest()
        assert manifest.tabletop is not None
        updated = []
        for item in manifest.tabletop.pieces:
            if item.id == piece_id:
                updated.append(TabletopPiece(id=piece_id, cell=coord, owner=item.owner))
            else:
                updated.append(item)
        if piece_id not in {item.id for item in updated}:
            updated.append(TabletopPiece(id=piece_id, cell=coord, owner=piece.owner))
        manifest.tabletop.pieces = updated
        self._commit(manifest)

    def cell_of(self, node_id: str) -> tuple[int, int] | None:
        node = self.scene._graph_nodes().get(node_id)
        if node is None:
            return None
        cell = node.meta.get("cell")
        if isinstance(cell, (list, tuple)) and len(cell) >= 2:
            return int(cell[0]), int(cell[1])
        if node_id.startswith("cell_"):
            try:
                _, col_s, row_s = node_id.split("_", 2)
                return int(col_s), int(row_s)
            except ValueError:
                return None
        return None

    def piece_at(self, cell: tuple[int, int] | list[int]) -> str | None:
        coord = self._cell(cell)
        for piece_id, piece in self._pieces.items():
            if piece.cell == coord:
                return piece_id
        for node in self.scene._graph_nodes().values():
            if node.meta.get("boardRole") != "piece":
                continue
            cell_meta = node.meta.get("cell")
            if isinstance(cell_meta, (list, tuple)) and (int(cell_meta[0]), int(cell_meta[1])) == coord:
                return node.id
        return None

    def empty_cells(self) -> list[tuple[int, int]]:
        occupied = {self._cell(piece.cell) for piece in self._pieces.values()}
        cells: list[tuple[int, int]] = []
        for col in range(self.cols):
            for row in range(self.rows):
                if (col, row) not in occupied:
                    cells.append((col, row))
        return cells

    def neighbors(self, cell: tuple[int, int], *, diagonal: bool = False) -> list[tuple[int, int]]:
        col, row = self._cell(cell)
        deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if diagonal:
            deltas.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])
        result: list[tuple[int, int]] = []
        for dx, dy in deltas:
            next_cell = (col + dx, row + dy)
            if 0 <= next_cell[0] < self.cols and 0 <= next_cell[1] < self.rows:
                result.append(next_cell)
        return result

    def cell_id(self, cell: tuple[int, int]) -> str:
        col, row = self._cell(cell)
        return f"cell_{col}_{row}"

    def cell_position(
        self, cell: tuple[int, int] | list[int], *, y: float | None = None
    ) -> tuple[float, float, float]:
        col, row = self._cell(cell)
        x = (col - (self.cols - 1) / 2.0) * self.cell_size + self.origin[0]
        z = (row - (self.rows - 1) / 2.0) * self.cell_size + self.origin[2]
        return (x, self.origin[1] if y is None else y, z)

    def in_bounds(self, cell: tuple[int, int] | list[int]) -> bool:
        col, row = int(cell[0]), int(cell[1])
        return 0 <= col < self.cols and 0 <= row < self.rows

    def _handle_event(self, scene: Scene, event: SemanticEvent) -> None:
        del scene
        if event.name in {"match_started", "game_started"}:
            self._reset_match()
            return
        if event.name != "node_picked" or not event.node_id:
            return
        pick = self._resolve_pick(event.node_id)
        if self._on_pick is None:
            self._sandbox_pick(pick)
            return
        self._on_pick(self, pick)

    def _sandbox_pick(self, pick: BoardPick) -> None:
        """Default: select a piece, then move it to any empty highlighted cell."""
        if pick.kind == "piece":
            self.select(pick.node_id)
            self.highlight(self.empty_cells())
            return
        if pick.kind == "cell" and self.selected_id and pick.cell is not None:
            if pick.cell in self.highlights or pick.node_id in self._tabletop_highlights():
                self.move(self.selected_id, pick.cell)
                self.clear_highlights()
                self.next_turn()

    def _resolve_pick(self, node_id: str) -> BoardPick:
        node = self.scene._graph_nodes().get(node_id)
        role = None if node is None else node.meta.get("boardRole")
        cell = self.cell_of(node_id)
        if role == "piece" or node_id in self._pieces:
            return BoardPick(node_id=node_id, kind="piece", cell=cell)
        if role == "cell" or (node_id.startswith("cell_") and cell is not None):
            return BoardPick(node_id=node_id, kind="cell", cell=cell)
        return BoardPick(node_id=node_id, kind="other", cell=cell)

    def _reset_match(self) -> None:
        manifest = self._manifest()
        manifest.match.phase = "playing"
        if manifest.tabletop is not None:
            manifest.tabletop.turn = 0
            manifest.tabletop.selected_id = None
            manifest.tabletop.highlights = []
        self._commit(manifest)

    def _build_cells(self) -> None:
        thickness = 0.08
        for col in range(self.cols):
            for row in range(self.rows):
                node_id = self.cell_id((col, row))
                color = self.light if (col + row) % 2 == 0 else self.dark
                position = self.cell_position((col, row), y=self.origin[1])
                node = self.scene.create_primitive(
                    node_id,
                    "box",
                    size=(self.cell_size * 0.96, thickness, self.cell_size * 0.96),
                    position=position,
                    material=Material(color),
                    physics=Physics(body="fixed", collider="cuboid", sensor=True),
                    tags=["board-cell"],
                )
                node.meta["cell"] = [col, row]
                node.meta["boardRole"] = "cell"

    def _cell(self, cell: tuple[int, int] | list[int]) -> tuple[int, int]:
        if len(cell) < 2:
            raise ValueError("A board cell needs two indices (col, row)")
        coord = (int(cell[0]), int(cell[1]))
        if not self.in_bounds(coord):
            raise ValueError(f"Cell {coord} is outside the {self.cols}x{self.rows} board")
        return coord

    def _manifest(self) -> ExperienceManifest:
        raw = self.scene._experience
        if not isinstance(raw, dict):
            raise RuntimeError("Board is missing an experience manifest")
        return ExperienceManifest.from_dict(raw)

    def _commit(self, manifest: ExperienceManifest) -> None:
        manifest.touch()
        self.scene.set_experience(manifest)

    def _tabletop(self):
        manifest = self._manifest()
        return manifest.tabletop

    def _tabletop_highlights(self) -> list[str]:
        tabletop = self._tabletop()
        return [] if tabletop is None else list(tabletop.highlights)


def _resolve_piece_mesh(
    asset: str | None, source: str | Path | None
) -> tuple[str, str | None]:
    """Return (glb path, catalog id or None) for a mesh piece."""
    if source is not None:
        return str(source), asset
    if asset is None:
        raise ValueError("place() needs asset or source for a mesh piece")
    catalog_file = Path.cwd() / "assets.catalog.json"
    if catalog_file.is_file():
        try:
            item = AssetCatalog.load(catalog_file).get(asset)
        except KeyError:
            item = None
        if item is not None and item.path:
            return item.path, item.id
    path = Path(asset)
    if path.suffix.lower() in {".glb", ".gltf"}:
        return str(path), None
    raise ValueError(
        f"Unknown catalog asset {asset!r}. Pass source= to a .glb "
        "or add it to assets.catalog.json."
    )
