import { beforeEach, describe, expect, it, vi } from "vitest";

describe("runtime config helpers", () => {
  beforeEach(() => {
    vi.resetModules();
    window.__SCENEIFY_CONFIG__ = undefined;
  });

  it("prefixes api and websocket urls from apiBase", async () => {
    window.__SCENEIFY_CONFIG__ = { apiBase: "http://127.0.0.1:9000" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false }) as Response),
    );
    const { loadConfig, apiUrl, wsUrl, resolveAssetUrl } = await import("./config");
    await loadConfig();
    expect(apiUrl("/api/scene")).toBe("http://127.0.0.1:9000/api/scene");
    expect(wsUrl("/api/realtime")).toBe("ws://127.0.0.1:9000/api/realtime");
    expect(resolveAssetUrl("props/crate.glb")).toBe(
      "http://127.0.0.1:9000/api/asset?path=props%2Fcrate.glb",
    );
  });

  it("serves packed assets from the static host in static mode", async () => {
    window.__SCENEIFY_CONFIG__ = {
      apiBase: "http://127.0.0.1:9000",
      assetMode: "static",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false }) as Response),
    );
    const { loadConfig, resolveAssetUrl } = await import("./config");
    await loadConfig();
    expect(resolveAssetUrl("assets/crate.glb")).toBe("/assets/crate.glb");
    expect(resolveAssetUrl("https://cdn.example.com/a.glb")).toBe(
      "https://cdn.example.com/a.glb",
    );
  });
});
