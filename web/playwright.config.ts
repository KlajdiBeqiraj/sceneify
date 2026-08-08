import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:4173", trace: "retain-on-failure" },
  webServer: [
    {
      command: "uv run python ../tests/e2e_server.py",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: true,
    },
    {
      command: "uv run python ../tests/e2e_server.py --play --port 4174",
      url: "http://127.0.0.1:4174",
      reuseExistingServer: true,
    },
    {
      command: "uv run python ../tests/e2e_server.py --roman --port 4175",
      url: "http://127.0.0.1:4175",
      reuseExistingServer: true,
    },
    {
      command: "uv run python ../tests/e2e_server.py --roman --edit --port 4176",
      url: "http://127.0.0.1:4176",
      reuseExistingServer: true,
    },
    {
      command: "uv run python ../tests/e2e_server.py --stress --port 4177",
      url: "http://127.0.0.1:4177",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
