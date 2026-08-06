import type { ScenePayload } from "../types/scene";

export async function fetchScene(): Promise<ScenePayload> {
  const response = await fetch("/api/scene");
  if (!response.ok) {
    throw new Error(`Failed to load scene (${response.status})`);
  }
  return response.json();
}

export function assetUrl(source: string): string {
  if (/^https?:\/\//i.test(source)) {
    return source;
  }
  return `/api/asset?path=${encodeURIComponent(source)}`;
}

export type NodePatch = {
  position?: number[];
  rotation?: number[];
  scale?: number[];
  visible?: boolean;
  apply_environment?: boolean;
};

export async function patchNode(
  nodeId: string,
  patch: NodePatch,
): Promise<{ scene: ScenePayload }> {
  const response = await fetch(`/api/nodes/${encodeURIComponent(nodeId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to patch node (${response.status})`);
  }
  return response.json();
}

export async function saveScene(path: string): Promise<string> {
  const response = await fetch("/api/scene/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!response.ok) {
    throw new Error(`Failed to save scene (${response.status})`);
  }
  const data = await response.json();
  return data.saved as string;
}
