import { apiUrl, resolveAssetUrl } from "../config";
import type { Material, Physics, ScenePayload } from "../types/scene";

export class RevisionConflict extends Error {
  constructor() {
    super("Scene changed on the server. Reloading the latest revision.");
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(url), init);
  if (response.status === 409) {
    throw new RevisionConflict();
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function fetchScene(): Promise<ScenePayload> {
  return request<ScenePayload>("/api/scene");
}

export function assetUrl(source: string): string {
  return resolveAssetUrl(source);
}

export type CatalogAsset = {
  id: string;
  name?: string;
  path?: string;
  source?: string;
  format: string;
  license?: string;
  checksum?: string;
  thumbnail?: string;
  byteSize?: number;
  animations?: string[];
  tags?: string[];
  metadata?: Record<string, unknown>;
};

export type NodePatch = {
  label?: string;
  position?: number[];
  rotation?: number[];
  scale?: number[];
  visible?: boolean;
  parentId?: string | null;
  tags?: string[];
  material?: Material;
  physics?: Physics;
  apply_environment?: boolean;
};

export async function patchNode(
  nodeId: string,
  patch: NodePatch,
  revision?: number,
): Promise<{ scene: ScenePayload }> {
  return request(`/api/nodes/${encodeURIComponent(nodeId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...patch, revision }),
  });
}

export async function sceneCommand(
  command: string,
  payload: Record<string, unknown> = {},
  revision?: number,
): Promise<{ scene: ScenePayload; commandId?: string }> {
  return request("/api/scene/commands", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, revision, ...payload }),
  });
}

export async function importGlb(file: File, revision?: number): Promise<{ scene: ScenePayload }> {
  const body = new FormData();
  body.append("file", file);
  if (revision !== undefined) body.append("revision", String(revision));
  return request("/api/assets/import", { method: "POST", body });
}

export async function fetchCatalog(query = "", tags: string[] = []): Promise<CatalogAsset[]> {
  const params = new URLSearchParams({ q: query });
  tags.forEach((tag) => params.append("tag", tag));
  return request<CatalogAsset[]>(`/api/assets?${params}`);
}

export async function saveScene(path: string, revision?: number): Promise<string> {
  const data = await request<{ saved: string }>("/api/scene/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, revision }),
  });
  return data.saved;
}

export type SourceSyncReport = {
  mode: string;
  patchable: boolean;
  patchableIds?: string[];
  patchable_ids?: string[];
  blockers: string[];
  hasMarkers?: boolean;
  has_markers?: boolean;
  scriptPath?: string | null;
  script_path?: string | null;
};

export async function fetchSourceSync(path: string): Promise<SourceSyncReport> {
  return request<SourceSyncReport>(`/api/scene/source-sync?path=${encodeURIComponent(path)}`);
}

export async function savePythonScene(
  path: string,
  revision?: number,
  mode: "auto" | "markers" | "ast" = "auto",
): Promise<{ saved: string; sync: SourceSyncReport }> {
  return request("/api/scene/save-python", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, revision, mode }),
  });
}
