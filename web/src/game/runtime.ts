import type { GameplayRole, PrimitiveNode, ScenePayload } from "../types/scene";

export type ControllerPreset = "simple" | "ecctrl";

export type RuntimeConfig = {
  title: string;
  seconds: number;
  requiredScore: number;
  playerNodeId: string | null;
  moveSpeed: number;
  jumpSpeed: number;
  cameraDistance: number;
  cameraHeight: number;
  controllerPreset: ControllerPreset;
  sprintMult: number;
};

export function gameplayRoles(scene: ScenePayload): Map<string, GameplayRole> {
  const roles = new Map<string, GameplayRole>();
  const game = scene.game;
  game?.controllers?.forEach(({ nodeId }) => roles.set(nodeId, "player"));
  game?.collectibles?.forEach(({ nodeId }) => roles.set(nodeId, "pickup"));
  game?.hazards?.forEach(({ nodeId }) => roles.set(nodeId, "hazard"));
  game?.checkpoints?.forEach(({ nodeId }) => roles.set(nodeId, "checkpoint"));
  game?.goals?.forEach(({ nodeId }) => roles.set(nodeId, "goal"));
  return roles;
}

export function runtimeConfig(scene: ScenePayload): RuntimeConfig {
  const controller = scene.game?.controllers?.[0];
  const camera = scene.game?.cameras?.[0];
  const requiredByGoal = scene.game?.goals
    ?.map((goal) => goal.requiredScore)
    .find((value): value is number => typeof value === "number");
  const preset = controller?.preset === "ecctrl" ? "ecctrl" : "simple";
  return {
    title: scene.game?.hud?.title ?? "Collect & Escape",
    seconds: scene.game?.timer?.seconds ?? 90,
    requiredScore: requiredByGoal ?? scene.game?.collectibles?.length ?? 0,
    playerNodeId: controller?.nodeId ?? null,
    moveSpeed: controller?.moveSpeed ?? 5,
    jumpSpeed: controller?.jumpSpeed ?? 6,
    cameraDistance: camera?.distance ?? 6,
    cameraHeight: camera?.height ?? 3,
    controllerPreset: preset,
    sprintMult: controller?.sprintMult ?? 2,
  };
}

export function primitiveById(scene: ScenePayload, id: string | null): PrimitiveNode | undefined {
  return id ? (scene.primitives ?? []).find((node) => node.id === id) : undefined;
}
