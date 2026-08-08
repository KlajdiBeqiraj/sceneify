import { expect, test, type Page } from "@playwright/test";

type PerfSample = {
  fps: number;
  calls: number;
  triangles: number;
  geometries: number;
  textures: number;
  minFps: number;
  samples: number;
  meshObjects: number;
  instancedMeshes: number;
  instancedCount: number;
};

const STRESS_URL = "http://127.0.0.1:4177/?perf=1";
const REPEAT_MESHES = Number(process.env.SCENEIFY_STRESS_COUNT || 200);

/** Headless WebGL budgets — tighten locally with SCENEIFY_PERF_STRICT=1. */
const STRICT = process.env.SCENEIFY_PERF_STRICT === "1";
const TARGETS = {
  minFps: STRICT ? 50 : 30,
  // Structural: barrels must be instanced, not N cloned scene graphs.
  minInstancedCount: REPEAT_MESHES,
  maxMeshObjects: STRICT ? 30 : 60,
  // Optional GPU counters (often 0 in headless Angle); enforced only when > 0.
  maxDrawCalls: STRICT ? 50 : 100,
};

test.use({
  launchOptions: {
    args: ["--use-gl=angle", "--enable-webgl", "--ignore-gpu-blocklist"],
  },
});

test.describe.configure({ timeout: 90_000 });

async function waitForPerf(page: Page, minSamples = 4): Promise<PerfSample> {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(STRESS_URL, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("Stress Many Assets")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("canvas")).toBeVisible({ timeout: 30_000 });
  await page.waitForFunction(
    (needed) => {
      const sample = (window as unknown as { __SCENEIFY_PERF__?: PerfSample }).__SCENEIFY_PERF__;
      return Boolean(sample && sample.samples >= needed && sample.fps > 0);
    },
    minSamples,
    { timeout: 60_000 },
  );
  // Wait until GLBs have mounted enough for instancing to appear.
  await page.waitForFunction(
    (needed) => {
      const sample = (window as unknown as { __SCENEIFY_PERF__?: PerfSample }).__SCENEIFY_PERF__;
      return Boolean(sample && sample.instancedCount >= needed);
    },
    REPEAT_MESHES,
    { timeout: 60_000 },
  );
  expect(errors.filter((message) => message.includes("R3F:"))).toEqual([]);
  const sample = await page.evaluate(() => {
    return (window as unknown as { __SCENEIFY_PERF__: PerfSample }).__SCENEIFY_PERF__;
  });
  expect(sample).toBeTruthy();
  return sample!;
}

test.describe("browser stress performance", () => {
  test("loads many repeated assets without page errors", async ({ page }) => {
    const sample = await waitForPerf(page, 3);
    const scene = await page.request.get("http://127.0.0.1:4177/api/scene");
    expect(scene.ok()).toBeTruthy();
    const payload = await scene.json();
    expect(payload.meshes.length).toBeGreaterThanOrEqual(REPEAT_MESHES);
    expect(sample.fps).toBeGreaterThan(0);
  });

  test("holds interactive FPS under asset stress", async ({ page }) => {
    await waitForPerf(page, 4);
    const canvas = page.locator("canvas");
    const box = await canvas.boundingBox();
    expect(box).toBeTruthy();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down({ button: "left" });
      await page.mouse.move(box.x + box.width / 2 + 140, box.y + box.height / 2, { steps: 16 });
      await page.mouse.up({ button: "left" });
    }
    await page.waitForTimeout(2500);
    const after = await page.evaluate(() => {
      return (window as unknown as { __SCENEIFY_PERF__: PerfSample }).__SCENEIFY_PERF__;
    });
    expect(after.minFps).toBeGreaterThanOrEqual(TARGETS.minFps);
    expect(after.fps).toBeGreaterThanOrEqual(TARGETS.minFps);
  });

  test("instances repeated assets instead of cloning each mesh", async ({ page }) => {
    const sample = await waitForPerf(page, 5);
    expect(sample.instancedMeshes).toBeGreaterThanOrEqual(1);
    expect(sample.instancedCount).toBeGreaterThanOrEqual(TARGETS.minInstancedCount);
    // Unique props + environment helpers may add meshes, but never ~80 barrel clones.
    expect(sample.meshObjects).toBeLessThanOrEqual(TARGETS.maxMeshObjects);
    if (sample.calls > 0) {
      expect(sample.calls).toBeLessThanOrEqual(TARGETS.maxDrawCalls);
      expect(sample.calls).toBeLessThan(REPEAT_MESHES * 0.45);
    }
    console.log(JSON.stringify({ target: TARGETS, sample }, null, 2));
  });
});
