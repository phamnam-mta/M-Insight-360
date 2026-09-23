import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "../tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.EB_TEST_BASE_URL ?? "http://localhost:8080",
    // The pre-installed browser bundle in this environment is pinned to a
    // specific Chromium build that may not match whatever @playwright/test
    // version npm resolves — launch that pinned binary directly rather
    // than the (unavailable) version-matched download.
    launchOptions: {
      executablePath: "/opt/pw-browsers/chromium",
    },
  },
});
