import { describe, expect, it } from "vitest";
import { canReparent, editorReducer, initialEditorState } from "./editorStore";
import type { ScenePayload } from "../types/scene";
import { gameplayRoles, runtimeConfig } from "../game/runtime";

const scene: ScenePayload = {
  schemaVersion: 2,
  revision: 4,
  name: "Test world",
  background: "#000",
  meshes: [],
  annotations: [],
  trajectories: [],
  primitives: [
    { kind: "primitive", id: "child", primitive: "box", parentId: "parent", position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], visible: true },
  ],
  objects: [
    { kind: "object", id: "parent", position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], visible: true },
  ],
  game: {
    controllers: [{ nodeId: "parent", moveSpeed: 7, jumpSpeed: 8 }],
    collectibles: [{ nodeId: "child", value: 2 }],
    hazards: [],
    checkpoints: [],
    goals: [{ nodeId: "exit", requiredScore: 2 }],
    hud: { title: "Manifest game" },
    timer: { seconds: 45 },
  },
};

describe("editor reducer", () => {
  it("tracks game transitions and score", () => {
    let state = editorReducer(initialEditorState, { type: "gameStart", timeLimit: 10 });
    state = editorReducer(state, { type: "gamePickup", id: "coin" });
    state = editorReducer(state, { type: "gamePickup", id: "coin" });
    state = editorReducer(state, { type: "gameTick", delta: 2 });
    expect(state).toMatchObject({ gamePhase: "playing", score: 1, timeLeft: 8, health: 3 });
    expect(editorReducer(state, { type: "gameWin" }).gamePhase).toBe("won");
  });

  it("applies combat damage until the run is lost", () => {
    let state = editorReducer(initialEditorState, { type: "gameStart", timeLimit: 20 });
    state = editorReducer(state, { type: "gameDamage", amount: 1 });
    expect(state).toMatchObject({ health: 2, gamePhase: "playing" });
    state = editorReducer(state, { type: "gameDamage", amount: 2 });
    expect(state).toMatchObject({ health: 0, gamePhase: "lost" });
  });

  it("prevents hierarchy cycles", () => {
    expect(canReparent(scene, "parent", "child")).toBe(false);
    expect(canReparent(scene, "child", null)).toBe(true);
  });

  it("derives roles and runtime settings from the v2 manifest", () => {
    expect(gameplayRoles(scene).get("parent")).toBe("player");
    expect(gameplayRoles(scene).get("child")).toBe("pickup");
    expect(runtimeConfig(scene)).toMatchObject({
      title: "Manifest game",
      seconds: 45,
      requiredScore: 2,
      moveSpeed: 7,
      jumpSpeed: 8,
    });
  });

  it("clears pickups, checkpoint, score and timer on restart", () => {
    let state = editorReducer(initialEditorState, { type: "gameStart", timeLimit: 20, spawn: [2, 3, 4] });
    state = editorReducer(state, { type: "gamePickup", id: "coin", value: 2 });
    state = editorReducer(state, { type: "checkpoint", position: [8, 1, 2] });
    const restarted = editorReducer(state, { type: "gameStart", timeLimit: 20, spawn: [2, 3, 4] });
    expect(restarted).toMatchObject({ score: 0, timeLeft: 20, checkpoint: [2, 3, 4], collectedIds: [] });
    expect(restarted.gameRun).toBeGreaterThan(state.gameRun);
  });
});
