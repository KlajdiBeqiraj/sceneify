import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("creates, saves, and reloads a primitive", async ({ page }) => {
  await expect(page.getByText("Collect and Escape")).toBeVisible();
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByRole("button", { name: "Box" }).click();
  await expect(page.getByText("Created box")).toBeVisible();
  await page.getByRole("button", { name: "Hierarchy" }).click();
  await expect(page.getByText("box", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/Saved/)).toBeVisible();
  await page.getByRole("button", { name: "Reload scene" }).click();
  await expect(page.getByText("Scene synchronized")).toBeVisible();
});

test("filters and instantiates a catalog GLB", async ({ page }) => {
  await page.getByRole("button", { name: "Assets" }).click();
  await expect(page.getByText("knight", { exact: true })).toBeVisible();
  await expect(page.getByText(/CC0-1.0/).first()).toBeVisible();
  await page.getByLabel("Filter by tag").fill("animated");
  await expect(page.getByText("knight", { exact: true })).toBeVisible();
  await expect(page.getByText("mage", { exact: true })).toBeVisible();
  await page.getByText("knight", { exact: true }).dblclick();
  await expect(page.getByText(/Added examples\/assets\/kaykit\/knight.glb/)).toBeVisible();
});

test("opens and starts the game runtime", async ({ page }) => {
  await page.getByRole("button", { name: "Play game" }).click();
  await expect(page.getByRole("button", { name: "Create" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Collect & Escape" })).toBeVisible();
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByText("Relics")).toBeVisible();
});

test("scene.play starts a standalone playable view", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  await page.goto("http://127.0.0.1:4174");
  await expect(page.getByRole("button", { name: "Create" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Collect & Escape" })).toBeVisible();
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByText(/Move: WASD/)).toBeVisible();
  await expect(page.getByText(/Attack: J/)).toBeVisible();
  await expect(page.getByText("Health")).toBeVisible();
  await page.waitForTimeout(800);
  const canvas = page.locator("canvas");
  const beforeMove = (await canvas.getAttribute("data-sceneify-player-position"))!
    .split(",")
    .map(Number);
  await expect(canvas).toHaveAttribute("data-sceneify-player-animation", "idle");
  await page.keyboard.down("w");
  await page.waitForTimeout(500);
  await expect(canvas).toHaveAttribute("data-sceneify-player-animation", "run");
  const facing = Number(await canvas.getAttribute("data-sceneify-player-facing"));
  expect(Math.abs(Math.abs(facing) - Math.PI)).toBeLessThan(0.35);
  await page.keyboard.up("w");
  const afterMove = (await canvas.getAttribute("data-sceneify-player-position"))!
    .split(",")
    .map(Number);
  expect(afterMove[2]).toBeLessThan(beforeMove[2] - 1);
  // Strafe into a side wall collider and verify the player cannot leave the arena.
  await page.keyboard.down("a");
  await page.waitForTimeout(1800);
  await page.keyboard.up("a");
  const againstWall = (await canvas.getAttribute("data-sceneify-player-position"))!
    .split(",")
    .map(Number);
  expect(againstWall[0]).toBeGreaterThan(-9.5);
  expect(browserErrors).toEqual([]);
});

test("renders the Roman GLB environment as a clean standalone view", async ({ page, request }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const asset = await request.get(
    "http://127.0.0.1:4175/api/asset?path=examples/assets/roman/marble_bust.glb",
  );
  expect(asset.ok()).toBe(true);
  await page.goto("http://127.0.0.1:4175");
  await expect(page.getByRole("button", { name: "Create" })).toHaveCount(0);
  await expect(page.locator("canvas")).toBeVisible();
  await expect(page.getByText("Automatic camera tour")).toBeVisible();
  // Guided tour starts automatically and eventually reaches the fountain exhibit.
  await expect(page.locator("canvas")).toHaveAttribute("data-sceneify-tour-stop", /.+/);
  await expect
    .poll(async () => page.locator("canvas").getAttribute("data-sceneify-poi-focus"), {
      timeout: 25000,
    })
    .toBe("poi_fountain");
  await expect(page.locator("[data-poi-focus-panel='poi_fountain']")).toBeVisible();
  await expect(page.getByText("The civic fountain")).toBeVisible();
  await expect(page.locator(".poi-tour-cue")).toHaveText(/Tight FOV push|daylight readable/i);
  expect(browserErrors).toEqual([]);
});

test("opens the Roman environment in authoring mode", async ({ page }) => {
  await page.goto("http://127.0.0.1:4176");
  await expect(page.getByRole("button", { name: "Create" })).toBeVisible();
  await expect(page.getByText("Roman Forum Explorer")).toBeVisible();
  await expect(page.getByText("piazza", { exact: true })).toBeVisible();
  await expect(page.locator("canvas")).toBeVisible();
  const marker = page.getByRole("button", { name: "Point of interest: Marble Bust 01" });
  const before = await marker.boundingBox();
  expect(before).not.toBeNull();
  const status = await page.evaluate(async () => {
    const scene = await fetch("/api/scene").then((response) => response.json());
    const response = await fetch("/api/nodes/marble_bust", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ position: [-1.2, 1.25, 2.8], revision: scene.revision }),
    });
    return response.status;
  });
  expect(status).toBe(200);
  await expect.poll(async () => {
    const current = await marker.boundingBox();
    return Math.abs((current?.x ?? 0) - (before?.x ?? 0));
  }).toBeGreaterThan(10);
});
