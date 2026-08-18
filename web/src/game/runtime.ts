import type {
  ExperienceManifest,
  GameManifest,
  GameplayRole,
  PrimitiveNode,
  RuntimeSlot,
  ScenePayload,
} from "../types/scene";

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

export function sceneExperience(scene: ScenePayload): ExperienceManifest | null {
  if (scene.experience) return scene.experience;
  if (scene.game) {
    return {
      family: "character",
      runtimeSlot: "character_world",
      interaction: { primary: "overlap" },
      character: scene.game,
      hud: {
        enabled: true,
        title: scene.game.hud?.title,
        hint: scene.game.hud?.controlsHint,
        description: scene.game.hud?.description,
      },
    };
  }
  return null;
}

export function runtimeSlot(scene: ScenePayload): RuntimeSlot {
  const experience = sceneExperience(scene);
  if (experience?.runtimeSlot) return experience.runtimeSlot;
  if (experience?.family === "board") return "tabletop";
  if (experience?.family === "character" || scene.game) return "character_world";
  if (experience?.family === "present") return "present";
  return "none";
}

export function characterManifest(scene: ScenePayload): GameManifest | null {
  return sceneExperience(scene)?.character ?? scene.game ?? null;
}

export function gameplayRoles(scene: ScenePayload): Map<string, GameplayRole> {
  const roles = new Map<string, GameplayRole>();
  const game = characterManifest(scene);
  game?.controllers?.forEach(({ nodeId }) => roles.set(nodeId, "player"));
  game?.collectibles?.forEach(({ nodeId }) => roles.set(nodeId, "pickup"));
  game?.hazards?.forEach(({ nodeId }) => roles.set(nodeId, "hazard"));
  game?.checkpoints?.forEach(({ nodeId }) => roles.set(nodeId, "checkpoint"));
  game?.goals?.forEach(({ nodeId }) => roles.set(nodeId, "goal"));
  return roles;
}

export function runtimeConfig(scene: ScenePayload): RuntimeConfig {
  const game = characterManifest(scene);
  const experience = sceneExperience(scene);
  const controller = game?.controllers?.[0];
  const camera = game?.cameras?.[0];
  const requiredByGoal = game?.goals
    ?.map((goal) => goal.requiredScore)
    .find((value): value is number => typeof value === "number");
  const preset = controller?.preset === "ecctrl" ? "ecctrl" : "simple";
  return {
    title: experience?.hud?.title ?? game?.hud?.title ?? "Collect & Escape",
    seconds: game?.timer?.seconds ?? 90,
    requiredScore: requiredByGoal ?? game?.collectibles?.length ?? 0,
    playerNodeId: controller?.nodeId ?? null,
    moveSpeed: controller?.moveSpeed ?? 5,
    jumpSpeed: controller?.jumpSpeed ?? 6,
    cameraDistance: camera?.distance ?? experience?.camera?.distance ?? 6,
    cameraHeight: camera?.height ?? experience?.camera?.height ?? 3,
    controllerPreset: preset,
    sprintMult: controller?.sprintMult ?? 2,
  };
}

export function primitiveById(scene: ScenePayload, id: string | null): PrimitiveNode | undefined {
  return id ? (scene.primitives ?? []).find((node) => node.id === id) : undefined;
}
