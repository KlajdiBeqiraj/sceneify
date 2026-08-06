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

export type ScenePayload = {
  name: string;
  background: string;
  meshes: MeshNode[];
  objects: ObjectNode[];
  annotations: AnnotationNode[];
  trajectories: TrajectoryNode[];
};
