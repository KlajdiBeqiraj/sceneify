export type SceneifyRuntimeConfig = {
  /** Backend origin, e.g. http://127.0.0.1:8765. Empty = same origin. */
  apiBase?: string;
  /** Optional bootstrap scene file next to the viewer. */
  sceneFile?: string;
  /** Prefer packed ./assets paths when present; otherwise use backend /api/asset. */
  assetMode?: "api" | "static";
  /** Embed chrome: none hides editor UI, grid, and gizmos. */
  chrome?: "none" | "minimal" | "editor";
  /** look = present/orbit; play = character/board HUD. */
  mode?: "look" | "play";
};

declare global {
  interface Window {
    __SCENEIFY_CONFIG__?: SceneifyRuntimeConfig;
  }
}

let config: SceneifyRuntimeConfig = {};
let loaded = false;

export function getConfig(): SceneifyRuntimeConfig {
  return config;
}

export async function loadConfig(): Promise<SceneifyRuntimeConfig> {
  if (loaded) return config;
  const inline = window.__SCENEIFY_CONFIG__;
  if (inline && typeof inline === "object") {
    config = { ...inline };
  }
  try {
    const response = await fetch("/sceneify.config.json", { cache: "no-store" });
    if (response.ok) {
      const file = (await response.json()) as SceneifyRuntimeConfig;
      config = { ...config, ...file };
    }
  } catch {
    // Same-origin / offline: keep inline or empty defaults.
  }
  const params = new URLSearchParams(window.location.search);
  const apiBase = params.get("apiBase");
  const mode = params.get("mode");
  const chrome = params.get("chrome");
  if (apiBase) config.apiBase = apiBase;
  if (mode === "look" || mode === "play") config.mode = mode;
  if (chrome === "none" || chrome === "minimal" || chrome === "editor") config.chrome = chrome;
  loaded = true;
  return config;
}

export function apiUrl(path: string): string {
  const base = (config.apiBase ?? "").replace(/\/$/, "");
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalized}`;
}

export function wsUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const base = (config.apiBase ?? "").replace(/\/$/, "");
  if (!base) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${normalized}`;
  }
  const url = new URL(base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = normalized;
  url.search = "";
  url.hash = "";
  return url.toString();
}

export function resolveAssetUrl(source: string): string {
  if (/^https?:\/\//i.test(source)) {
    return source;
  }
  const cleaned = source.replace(/^\.\//, "");
  if (
    (config.assetMode ?? "api") === "static" &&
    (cleaned.startsWith("assets/") || cleaned.startsWith("/assets/"))
  ) {
    return cleaned.startsWith("/") ? cleaned : `/${cleaned}`;
  }
  return apiUrl(`/api/asset?path=${encodeURIComponent(source)}`);
}
