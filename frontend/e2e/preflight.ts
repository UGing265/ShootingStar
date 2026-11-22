import { readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import path from "node:path";
import type { FullConfig } from "@playwright/test";

export function restoreNextEnv(): void {
  for (const [file, snapshot] of [
    [process.env.E2E_NEXT_ENV_PATH, process.env.E2E_NEXT_ENV_SNAPSHOT],
    [process.env.E2E_TSCONFIG_PATH, process.env.E2E_TSCONFIG_SNAPSHOT],
  ]) {
    if (file && snapshot !== undefined && readFileSync(file, "utf8").includes(".next-e2e")) {
      writeFileSync(file, Buffer.from(snapshot, "base64"));
    }
  }
}

export default async function preflight(config?: FullConfig): Promise<void> {
  if (config && process.env.E2E_PREFLIGHT_COMPLETE === "true") {
    restoreNextEnv();
    return;
  }
  if (config) process.env.E2E_PREFLIGHT_COMPLETE = "true";
  const shellKey = process.env.SHOOTINGSTAR_ADMIN_KEY;
  if (shellKey !== undefined) {
    let fileKey: string | undefined;
    try {
      const env = readFileSync(path.resolve(process.cwd(), path.basename(process.cwd()) === "frontend" ? "../.env" : ".env"), "utf8");
      for (const line of env.split(/\r?\n/)) {
        const entry = line.trim();
        const separator = entry.indexOf("=");
        if (!entry.startsWith("#") && separator >= 0 && entry.slice(0, separator).trim() === "SHOOTINGSTAR_ADMIN_KEY" && fileKey === undefined) {
          fileKey = entry.slice(separator + 1).trim().replace(/^['"]+|['"]+$/g, "");
        }
      }
    } catch {
      throw new Error("Cannot read repository .env to check SHOOTINGSTAR_ADMIN_KEY.");
    }
    const match = fileKey !== undefined && shellKey === fileKey;
    console.log(`SHOOTINGSTAR_ADMIN_KEY set: true, match: ${match}`);
    if (!match) throw new Error("Unset SHOOTINGSTAR_ADMIN_KEY in the shell and retry.");
  } else {
    console.log("SHOOTINGSTAR_ADMIN_KEY set: false");
  }
  if (!process.env.E2E_SNAPSHOT_ID) throw new Error("Set E2E_SNAPSHOT_ID to an existing snapshot ID.");

  // Playwright starts webServer plugins before globalSetup; check ports before starting them.
  if (!config) {
    for (const port of [8100, 3100]) {
      const { promise, resolve, reject } = Promise.withResolvers<void>();
      const server = createServer();
      server.once("error", () => reject(new Error(`Port ${port} is unavailable.`)));
      server.listen({ port, host: "127.0.0.1", exclusive: true }, () => server.close(() => resolve()));
      await promise;
    }
  }
}
