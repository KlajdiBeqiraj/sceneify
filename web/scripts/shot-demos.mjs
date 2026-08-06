import { chromium } from "@playwright/test";
import path from "path";
import fs from "fs";

const outDir = "/tmp/sceneify-shots";
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

async function waitReady(url) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Server not ready: ${url}`);
}

async function shot(name, url, prepare) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  if (prepare) await prepare(page);
  await page.waitForTimeout(1400);
  const file = path.join(outDir, name);
  await page.screenshot({ path: file, fullPage: true });
  console.log("wrote", file);
}

await waitReady("http://127.0.0.1:4174/");
await waitReady("http://127.0.0.1:4175/");

await shot("after-01-collect-menu.png", "http://127.0.0.1:4174");
await shot("after-02-collect-play.png", "http://127.0.0.1:4174", async (p) => {
  await p.getByRole("button", { name: "Start run" }).click();
  await p.waitForTimeout(1800);
});
await shot("after-03-collect-moved.png", "http://127.0.0.1:4174", async (p) => {
  await p.getByRole("button", { name: "Start run" }).click();
  await p.waitForTimeout(900);
  // Follow the safe left lane around the hazard pit.
  await p.keyboard.down("a");
  await p.waitForTimeout(500);
  await p.keyboard.up("a");
  await p.keyboard.down("w");
  await p.waitForTimeout(1600);
  await p.keyboard.up("w");
});
await shot("after-04-roman-overview.png", "http://127.0.0.1:4175");
await shot("after-05-roman-fountain-close.png", "http://127.0.0.1:4175", async (p) => {
  await p.waitForFunction(
    () => document.querySelector("canvas")?.dataset.sceneifyPoiFocus === "poi_fountain",
    null,
    { timeout: 30000 },
  );
  await p.waitForTimeout(1200);
});
await shot("after-06-roman-bust-dim.png", "http://127.0.0.1:4175", async (p) => {
  await p.waitForFunction(
    () => document.querySelector("canvas")?.dataset.sceneifyPoiFocus === "poi_bust",
    null,
    { timeout: 45000 },
  );
  await p.waitForTimeout(1200);
});
await shot("after-07-roman-horse-front.png", "http://127.0.0.1:4175", async (p) => {
  await p.waitForFunction(
    () => document.querySelector("canvas")?.dataset.sceneifyPoiFocus === "poi_horse",
    null,
    { timeout: 60000 },
  );
  await p.waitForTimeout(1200);
});
await shot("after-08-roman-arch-full.png", "http://127.0.0.1:4175", async (p) => {
  await p.waitForFunction(
    () => document.querySelector("canvas")?.dataset.sceneifyPoiFocus === "poi_ruins",
    null,
    { timeout: 60000 },
  );
  await p.waitForTimeout(1200);
});

await browser.close();
