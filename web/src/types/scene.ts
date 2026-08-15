export type Vec3 = [number, number, number];

export type Material = {
  color?: string;
  metalness?: number;
  roughness?: number;
  opacity?: number;
  wireframe?: boolean;
  baseColorTexture?: string | null;
  normalTexture?: string | null;
  metallicRoughnessTexture?: string | null;
  textureRepeat?: [number, number];
};

export type Physics = {
  body?: "fixed" | "dynamic" | "kinematic";
  collider?: "cuboid" | "ball" | "capsule" | "hull";
  mass?: number;
  sensor?: boolean;
};

export type AnimationConfig = {
  autoplay?: string;
  states?: Partial<Record<"idle" | "move" | "run" | "jump" | "attack" | "hit" | "death", string>>;
  loop?: boolean;
  fadeSeconds?: number;
};

export type NodeMeta = {
  animation?: AnimationConfig;
  visualFor?: string;
  renderPrimitive?: boolean;
  includeNodes?: string[];
  normalizeOrigin?: boolean;
  [key: string]: unknown;
};

export type GameplayRole =
  | "none"
  | "player"
  | "pickup"
  | "hazard"
  | "checkpoint"
  | "goal";

export type NodeFields = {
  parentId?: string | null;
  tags?: string[];
  material?: Material;
  physics?: Physics;
  meta?: NodeMeta;
};

export type MeshNode = {
  kind: "mesh";
  id: string;
  source: string;
  format?: string | null;
  position: number[];
  rotation: number[];
  scale: number[];
  visible: boolean;
} & NodeFields;

export type ObjectNode = {
  kind: "object";
  id: string;
  label?: string | null;
  children?: string[];
  position: number[];
  rotation: number[];
  scale: number[];
  visible: boolean;
} & NodeFields;

export type PrimitiveNode = {
  kind: "primitive";
  id: string;
  label?: string | null;
  primitive: "box" | "sphere" | "capsule" | "plane";
  size?: number[];
  radius?: number;
  height?: number;
  position: number[];
  rotation: number[];
  scale: number[];
  visible: boolean;
} & NodeFields;

export type AnnotationNode = {
  kind: "annotation";
  id: string;
  position: number[];
  targetId?: string | null;
  offset?: number[];
  label?: string | null;
  description?: string | null;
  color: string;
  visible: boolean;
  meta?: {
    interaction?: {
      reveal?: "always" | "hover";
      clickEvent?: string;
      cursor?: "pointer" | "default";
    };
    category?: string;
    [key: string]: unknown;
  };
};

export type TrajectoryNode = {
  kind: "trajectory";
  id: string;
  points: number[][];
  color: string;
  lineWidth: number;
  closed: boolean;
  visible: boolean;
};

export type BoundsNode = {
  min: number[];
  max: number[];
  visible: boolean;
  color: string;
};

export type GroundNode = {
  y: number;
  visible: boolean;
  color: string;
};

export type SnapGridNode = {
  size: number[];
  visible: boolean;
};

export type WorldMeshNode = {
  source: string;
  format?: string | null;
  position: number[];
  rotation: number[];
  scale: number[];
  visible: boolean;
  collide: boolean;
};

export type ZoneNode = {
  id: string;
  role: "allowed" | "forbidden" | "marker";
  shape: "box";
  min: number[];
  max: number[];
  label?: string | null;
  visible: boolean;
  color: string;
  opacity: number;
};

export type RuleNode = {
  kind: string;
  mode: string;
  enabled: boolean;
};

export type EnvironmentPayload = {
  bounds: BoundsNode | null;
  ground: GroundNode | null;
  snapGrid: SnapGridNode | null;
  worldMesh?: WorldMeshNode | null;
  zones: ZoneNode[];
  rules: RuleNode[];
  showAxes: boolean;
};

export type ScenePayload = {
  schemaVersion?: number;
  version?: number;
  revision?: number;
  name: string;
  background: string;
  environment?: EnvironmentPayload | null;
  meshes: MeshNode[];
  objects: ObjectNode[];
  primitives?: PrimitiveNode[];
  annotations: AnnotationNode[];
  trajectories: TrajectoryNode[];
  game?: GameManifest | null;
  prefabs?: Array<{ id: string; rootId?: string; label?: string | null; [key: string]: unknown }>;
  presentation?: {
    environmentMap?: string | null;
    environmentPreset?: "apartment" | "city" | "dawn" | "forest" | "lobby" | "night" | "park" | "studio" | "sunset" | "warehouse" | null;
    grid?: boolean;
    helpers?: boolean;
    shadows?: boolean;
    exposure?: number;
    ambientIntensity?: number;
    keyLightIntensity?: number;
    title?: string;
    subtitle?: string;
    fog?: { color?: string; near?: number; far?: number } | null;
    camera?: { position?: Vec3; fov?: number; target?: Vec3 } | null;
    cameraTour?: {
      autoplay?: boolean;
      loop?: boolean;
      stops?: Array<{
        id: string;
        position: number[];
        target: number[];
        travel?: number;
        hold?: number;
        exposure?: number;
        lightScale?: number;
        spotlight?: boolean;
        fov?: number;
        annotationId?: string;
        cue?: string;
      }>;
    } | null;
  };
};

export type GameManifest = {
  actionMaps?: Record<string, unknown> | Array<Record<string, unknown>>;
  controllers?: Array<{
    nodeId: string;
    moveSpeed?: number;
    jumpSpeed?: number;
    preset?: "simple" | "ecctrl";
    sprintMult?: number;
    actionMap?: string;
    [key: string]: unknown;
  }>;
  cameras?: Array<{
    nodeId?: string;
    targetNodeId?: string;
    distance?: number;
    height?: number;
    smoothing?: number;
    [key: string]: unknown;
  }>;
  collectibles?: Array<{ nodeId: string; value?: number; [key: string]: unknown }>;
  hazards?: Array<{ nodeId: string; [key: string]: unknown }>;
  checkpoints?: Array<{ nodeId: string; [key: string]: unknown }>;
  goals?: Array<{ nodeId: string; requiredScore?: number; [key: string]: unknown }>;
  enemies?: {
    spawnPoints?: number[][];
    types?: Array<{
      kind: string;
      source: string;
      maxAlive?: number;
      intervalSeconds?: number;
      speed?: number;
      scale?: number;
      health?: number;
      contactDamage?: number;
      hitEvent?: string;
      animation?: { idle?: string; run?: string; hit?: string; death?: string; attack?: string };
    }>;
  } | null;
  hud?: {
    title?: string;
    showScore?: boolean;
    showHealth?: boolean;
    showTimer?: boolean;
    description?: string;
    controlsHint?: string;
    [key: string]: unknown;
  };
  timer?: { seconds?: number; [key: string]: unknown };
  win?: Record<string, unknown>;
  lose?: Record<string, unknown>;
};

export type EditableNode = MeshNode | ObjectNode | PrimitiveNode | AnnotationNode;

export type TransformMode = "translate" | "rotate" | "scale";

export type SnapSettings = {
  translation: number;
  rotationDegrees: number;
  scale: number;
};

export type ConnectionState = "connecting" | "connected" | "disconnected";
export type RuntimeMode = "edit" | "play";
export type GamePhase = "menu" | "playing" | "won" | "lost";
