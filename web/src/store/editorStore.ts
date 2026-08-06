import type { GamePhase, ScenePayload, SnapSettings, TransformMode } from "../types/scene";

export type EditorState = {
  scene: ScenePayload | null;
  selectedId: string | null;
  transformMode: TransformMode;
  snap: SnapSettings;
  leftPanel: "outliner" | "create" | "assets";
  leftOpen: boolean;
  inspectorOpen: boolean;
  gamePhase: GamePhase;
  score: number;
  health: number;
  maxHealth: number;
  timeLeft: number;
  checkpoint: [number, number, number];
  collectedIds: string[];
  gameRun: number;
};

export type EditorAction =
  | { type: "scene"; scene: ScenePayload }
  | { type: "select"; id: string | null }
  | { type: "transformMode"; mode: TransformMode }
  | { type: "snap"; snap: SnapSettings }
  | { type: "panel"; panel: EditorState["leftPanel"] }
  | { type: "toggleLeft" }
  | { type: "toggleInspector" }
  | { type: "gameStart"; timeLimit: number; spawn?: [number, number, number] }
  | { type: "gameTick"; delta: number }
  | { type: "gamePickup"; id: string; value?: number }
  | { type: "gameDamage"; amount?: number }
  | { type: "gameWin" }
  | { type: "gameLose" }
  | { type: "checkpoint"; position: [number, number, number] }
  | { type: "gameReset" };

export const initialEditorState: EditorState = {
  scene: null,
  selectedId: null,
  transformMode: "translate",
  snap: { translation: 0.25, rotationDegrees: 15, scale: 0.1 },
  leftPanel: "outliner",
  leftOpen: true,
  inspectorOpen: true,
  gamePhase: "menu",
  score: 0,
  health: 3,
  maxHealth: 3,
  timeLeft: 90,
  checkpoint: [0, 1, 0],
  collectedIds: [],
  gameRun: 0,
};

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "scene":
      return {
        ...state,
        scene: action.scene,
        selectedId:
          state.selectedId && allNodeIds(action.scene).has(state.selectedId)
            ? state.selectedId
            : null,
      };
    case "select":
      return { ...state, selectedId: action.id };
    case "transformMode":
      return { ...state, transformMode: action.mode };
    case "snap":
      return { ...state, snap: action.snap };
    case "panel":
      return { ...state, leftPanel: action.panel, leftOpen: true };
    case "toggleLeft":
      return { ...state, leftOpen: !state.leftOpen };
    case "toggleInspector":
      return { ...state, inspectorOpen: !state.inspectorOpen };
    case "gameStart":
      return {
        ...state,
        gamePhase: "playing",
        score: 0,
        health: state.maxHealth,
        timeLeft: action.timeLimit,
        checkpoint: action.spawn ?? [0, 1, 0],
        collectedIds: [],
        gameRun: state.gameRun + 1,
      };
    case "gameTick": {
      if (state.gamePhase !== "playing") return state;
      const timeLeft = Math.max(0, state.timeLeft - action.delta);
      return { ...state, timeLeft, gamePhase: timeLeft === 0 ? "lost" : "playing" };
    }
    case "gamePickup":
      if (state.collectedIds.includes(action.id)) return state;
      return {
        ...state,
        score: state.score + (action.value ?? 1),
        collectedIds: [...state.collectedIds, action.id],
      };
    case "gameDamage": {
      if (state.gamePhase !== "playing") return state;
      const health = Math.max(0, state.health - (action.amount ?? 1));
      return {
        ...state,
        health,
        gamePhase: health === 0 ? "lost" : "playing",
      };
    }
    case "gameWin":
      return { ...state, gamePhase: "won" };
    case "gameLose":
      return { ...state, gamePhase: "lost" };
    case "checkpoint":
      return { ...state, checkpoint: action.position };
    case "gameReset":
      return {
        ...state,
        gamePhase: "menu",
        score: 0,
        health: state.maxHealth,
        timeLeft: 90,
        checkpoint: [0, 1, 0],
        collectedIds: [],
        gameRun: state.gameRun + 1,
      };
    default:
      return state;
  }
}

export function allNodeIds(scene: ScenePayload): Set<string> {
  return new Set([
    ...scene.meshes.map(({ id }) => id),
    ...scene.objects.map(({ id }) => id),
    ...(scene.primitives ?? []).map(({ id }) => id),
    ...scene.annotations.map(({ id }) => id),
  ]);
}

export function canReparent(scene: ScenePayload, nodeId: string, parentId: string | null): boolean {
  if (!parentId) return true;
  if (nodeId === parentId) return false;
  const parentByChild = new Map<string, string>();
  scene.objects.forEach((node) => {
    node.children?.forEach((child) => parentByChild.set(child, node.id));
  });
  [...scene.meshes, ...scene.objects, ...(scene.primitives ?? [])].forEach((node) => {
    if (node.parentId) parentByChild.set(node.id, node.parentId);
  });
  let cursor: string | undefined = parentId;
  while (cursor) {
    if (cursor === nodeId) return false;
    cursor = parentByChild.get(cursor);
  }
  return true;
}
