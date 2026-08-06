export type Vec3 = [number, number, number];

export type MeshNode = {
  kind: "mesh";
  id: string;
  source: string;
  format?: string | null;
  position: number[];
  rotation: number[];
  scale: number[];
  visible: boolean;
  meta?: Record<string, unknown>;
};

export type ObjectNode = {
  kind: "object";
  id: string;
  label?: string | null;
  children: string[];
  position: number[];
  rotation: number[];
  scale: number[];
  visible: boolean;
};

export type AnnotationNode = {
  kind: "annotation";
  id: string;
  position: number[];
  label?: string | null;
  description?: string | null;
  color: string;
  visible: boolean;
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
  name: string;
  background: string;
  environment?: EnvironmentPayload | null;
  meshes: MeshNode[];
  objects: ObjectNode[];
  annotations: AnnotationNode[];
  trajectories: TrajectoryNode[];
};

export type EditableNode = MeshNode | ObjectNode | AnnotationNode;
