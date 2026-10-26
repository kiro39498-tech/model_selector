import { test, expect } from "@playwright/test";

/**
 * LIVE end-to-end tests (GATED).
 *
 * These exercise the REAL backend, Neon PostgreSQL, and the configured Qwen
 * endpoint. They are SKIPPED by default and only run when RUN_LIVE_TESTS=1 is
 * set AND a real backend is reachable.
 *
 * A passing live e2e test is evidence of live integration. A skipped test is
 * NOT evidence of integration.
 */

const LIVE = process.env.RUN_LIVE_TESTS === "1";

test.describe("Live e2e (gated)", () => {
  // Skip the whole suite unless explicitly enabled.
  test.beforeEach(() => {
    if (!LIVE) {
      test.skip(true, "Live e2e requires RUN_LIVE_TESTS=1 and a running backend.");
    }
  });

  test("health endpoints report real config status", async ({ page }) => {
    const res = await page.request.get("/api/v1/health");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("ai_configured");
    expect(body).toHaveProperty("db_configured");
  });

  test("full workflow against the real backend", async ({ page }) => {
    // 1. Create a project.
    const created = await page.request.post("/api/v1/projects", {
      data: {
        name: "Live E2E",
        initial_description:
          "A customer support assistant that classifies intent and drafts replies.",
      },
    });
    expect(created.ok()).toBeTruthy();
    const pid = (await created.json()).id;

    // 2. Discovery (real AI).
    const disc = await page.request.post(
      `/api/v1/projects/${pid}/requirements/discovery`,
      { data: { message: "It should classify intent and draft a reply." } }
    );
    expect(disc.ok()).toBeTruthy();

    // 3. Approve (may be blocked by unresolved critical requirements).
    const approve = await page.request.post(
      `/api/v1/projects/${pid}/requirements/approve`
    );
    if (approve.status() === 409) {
      test.skip(true, "Approval blocked by unresolved critical requirements.");
      return;
    }
    expect(approve.ok()).toBeTruthy();

    // 4. Analysis (real AI) — validated, structured result.
    const analysis = await page.request.post(
      `/api/v1/projects/${pid}/analysis`
    );
    expect(analysis.status()).toBe(202);
    const body = await analysis.json();
    expect(body.run.status).toBe("completed");
    expect(body.result).not.toBeNull();
    expect(body.result).toHaveProperty("components");
  });
});
