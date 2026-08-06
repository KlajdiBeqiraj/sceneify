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
