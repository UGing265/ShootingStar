import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { readFileSync } from "node:fs";
import { restoreNextEnv } from "./e2e/preflight";

if (!process.env.E2E_NEXT_ENV_PATH) {
  process.env.E2E_NEXT_ENV_PATH = path.resolve(__dirname, "next-env.d.ts");
  process.env.E2E_NEXT_ENV_SNAPSHOT = readFileSync(process.env.E2E_NEXT_ENV_PATH).toString("base64");
  process.env.E2E_TSCONFIG_PATH = path.resolve(__dirname, "tsconfig.json");
  process.env.E2E_TSCONFIG_SNAPSHOT = readFileSync(process.env.E2E_TSCONFIG_PATH).toString("base64");
  process.once("exit", restoreNextEnv);
}

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/preflight.ts",
  globalTeardown: "./e2e/preflight.ts",
  grepInvert: /@real-gemini/,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3100", ...devices["Desktop Chrome"] },
  webServer: [
    {
      command: `node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --experimental-strip-types -e "import('./frontend/e2e/preflight.ts').then(m => m.default()).catch(e => { console.log(e.message); process.exitCode = 1; })" && "${path.resolve(__dirname, "../backend/.venv/Scripts/python.exe")}" -m uvicorn shootingstar.api.app:app --host 127.0.0.1 --port 8100`,
      cwd: path.resolve(__dirname, ".."),
      url: "http://127.0.0.1:8100/health",
      stdout: "pipe",
      stderr: "pipe",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npx next dev -p 3100",
      url: "http://127.0.0.1:3100",
      stderr: "pipe",
      env: { SHOOTINGSTAR_API_URL: "http://127.0.0.1:8100", NEXT_DIST_DIR: ".next-e2e" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
