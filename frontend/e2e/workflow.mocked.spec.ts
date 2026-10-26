import { test, expect } from "@playwright/test";

/**
 * MOCKED end-to-end tests.
 *
 * These intercept the API via page.route() and return deterministic responses.
 * They do NOT require a real backend, Neon, or the Qwen endpoint. They verify
 * that the UI renders and behaves correctly for a given API response.
 *
 * A passing mocked e2e test is NOT evidence of live integration.
 */

const PROJECT_ID = "p1";

// A deterministic analysis result with three ranked recommendations.
const analysisResult = {
  run: {
    id: "run-1",
    project_id: PROJECT_ID,
    status: "completed",
    correlation_id: "c1",
    error: null,
    created_at: "2026-10-20T00:00:00Z",
  },
  result: {
    schema_version: "1.0",
    application_summary: "A customer support assistant.",
    confirmed_requirements: ["REQ-001"],
    remaining_uncertainties: [],
    components: [
      {
        component_id: "C-001",
        name: "Intent classification",
        purpose: "Classify the intent of a support message.",
        ai_required: true,
        recommended_approach: "slm",
        classification: "SLM",
        decision_rationale: "Routine classification suits an SLM.",
        evidence: ["Task is deterministic classification."],
        alternatives: ["deterministic rules"],
        risks: ["Misclassification on ambiguous input."],
        requirement_ids: ["REQ-001"],
        confidence: 0.7,
        unresolved_questions: [],
        model_recommendations: [
          {
            rank: 1,
            model_name: "Llama 3.1 8B",
            provider: "Meta",
            total_params: 8_000_000_000,
            classification: "SLM",
            deployment_option: "self_hosted",
            rationale: "Small and fast.",
            evidence: ["Official model card"],
            strengths: ["Low latency"],
            weaknesses: ["Limited reasoning"],
            cost: null,
            confidence: 0.7,
            unverified: [],
            source_links: ["https://ai.meta.com/llama/llama3_1/"],
            verified: true,
          },
          {
            rank: 2,
            model_name: "Mistral 7B",
            provider: "Mistral AI",
            total_params: 7_000_000_000,
            classification: "SLM",
            deployment_option: "self_hosted",
            rationale: "Permissive license.",
            evidence: [],
            strengths: [],
            weaknesses: [],
            cost: null,
            confidence: 0.6,
            unverified: [],
            source_links: [],
            verified: true,
          },
          {
            rank: 3,
            model_name: "Llama 3.1 70B",
            provider: "Meta",
            total_params: 70_000_000_000,
            classification: "SLM",
            deployment_option: "self_hosted",
            rationale: "Larger SLM.",
            evidence: [],
            strengths: [],
            weaknesses: [],
            cost: null,
            confidence: 0.5,
            unverified: ["benchmark not measured"],
            source_links: [],
            verified: false,
          },
        ],
      },
    ],
    risks: [],
    validation_plan: {},
    consistency_checks: [],
    implementation_roadmap: [],
  },
};

async function mockApi(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/projects", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: PROJECT_ID,
          name: "Test App",
          description: "",
          status: "discovery",
          initial_description: "d",
          created_at: "2026-10-20T00:00:00Z",
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: PROJECT_ID,
            name: "Test App",
            description: "",
            status: "discovery",
            initial_description: "d",
            created_at: "2026-10-20T00:00:00Z",
          },
        ]),
      });
    }
  });
  await page.route(`**/api/v1/projects/${PROJECT_ID}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: PROJECT_ID,
        name: "Test App",
        description: "",
        status: "approved",
        initial_description: "d",
        created_at: "2026-10-20T00:00:00Z",
      }),
    });
  });
  await page.route(
    `**/api/v1/projects/${PROJECT_ID}/requirements`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "r1",
            code: "REQ-001",
            description: "Classify intent.",
            category: "ai",
            source: "user",
            status: "confirmed",
            confidence: null,
            criticality: "medium",
            dependencies: [],
            acceptance_criteria: [],
          },
        ]),
      });
    }
  );
  await page.route(
    `**/api/v1/projects/${PROJECT_ID}/requirements/completeness`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          by_category: {
            business: 1,
            functional: 1,
            data: 1,
            non_functional: 1,
            ai: 1,
            operational: 1,
          },
          critical_unresolved: [],
          missing: [],
          ready_for_approval: true,
        }),
      });
    }
  );
  await page.route(
    `**/api/v1/projects/${PROJECT_ID}/requirements/approve`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "rv1", version: 1, status: "approved" }),
      });
    }
  );
  await page.route(
    `**/api/v1/projects/${PROJECT_ID}/analysis`,
    async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 202,
          contentType: "application/json",
          body: JSON.stringify(analysisResult),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([analysisResult.run]),
        });
      }
    }
  );
  await page.route(
    `**/api/v1/projects/${PROJECT_ID}/analysis/run-1`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(analysisResult),
      });
    }
  );
  await page.route("**/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        ai_configured: true,
        db_configured: true,
        classification_threshold_billions: 150,
      }),
    });
  });
}

test.describe("Mocked e2e: requirements-to-recommendation workflow", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("project creation and navigation to discovery", async ({ page }) => {
    await page.goto("/");
    await page.fill("#name", "Test App");
    await page.fill("#desc", "A support assistant that classifies intent.");
    await page.click("text=Start discovery");
    // Navigates to the discovery screen for the created project.
    await expect(page).toHaveURL(
      new RegExp(`/projects/${PROJECT_ID}/discovery`)
    );
  });

  test("discovery screen renders and shows captured requirements", async ({
    page,
  }) => {
    await page.goto(`/projects/${PROJECT_ID}/discovery`);
    await expect(
      page.getByText("Requirements discovery")
    ).toBeVisible();
    // The captured requirement is shown.
    await expect(page.getByText("REQ-001")).toBeVisible();
  });

  test("requirements review and approval", async ({ page }) => {
    await page.goto(`/projects/${PROJECT_ID}/requirements`);
    await expect(page.getByText("Review requirements")).toBeVisible();
    await expect(page.getByText("Classify intent.")).toBeVisible();
    // Approve button is enabled when ready_for_approval is true.
    const approve = page.getByRole("button", { name: /approve & analyze/i });
    await expect(approve).toBeEnabled();
    await approve.click();
    // Navigates to the architecture screen.
    await expect(page).toHaveURL(
      new RegExp(`/projects/${PROJECT_ID}/architecture`)
    );
  });

  test("architecture screen renders components", async ({ page }) => {
    await page.goto(`/projects/${PROJECT_ID}/architecture`);
    await expect(page.getByText("Architecture")).toBeVisible();
    // The component from the analysis is listed in the accessible list.
    await expect(
      page.getByRole("button", { name: "Intent classification" })
    ).toBeVisible();
  });

  test("model comparison renders three ranked recommendations", async ({
    page,
  }) => {
    await page.goto(`/projects/${PROJECT_ID}/models`);
    await expect(page.getByText("Model comparison")).toBeVisible();
    // Three ranked candidates.
    await expect(page.getByText("#1")).toBeVisible();
    await expect(page.getByText("#2")).toBeVisible();
    await expect(page.getByText("#3")).toBeVisible();
    // Model names.
    await expect(page.getByText("Llama 3.1 8B")).toBeVisible();
    await expect(page.getByText("Mistral 7B")).toBeVisible();
    await expect(page.getByText("Llama 3.1 70B")).toBeVisible();
  });

  test("classification and verified/unverified badges render", async ({
    page,
  }) => {
    await page.goto(`/projects/${PROJECT_ID}/models`);
    await expect(page.getByText("Model comparison")).toBeVisible();
    // SLM classification appears (exact match, first occurrence).
    await expect(page.getByText("SLM", { exact: true }).first()).toBeVisible();
    // Verified and unverified badges are distinguished (exact match).
    await expect(
      page.getByText("verified", { exact: true }).first()
    ).toBeVisible();
    await expect(page.getByText("unverified", { exact: true })).toBeVisible();
  });

  test("settings screen shows config status without secrets", async ({
    page,
  }) => {
    await page.goto(`/projects/${PROJECT_ID}/settings`);
    await expect(page.getByText("Project settings")).toBeVisible();
    // "configured" appears for both AI and DB; assert at least one is visible.
    await expect(page.getByText("configured", { exact: true }).first()).toBeVisible();
    // No secret values are exposed.
    await expect(page.getByText("AI_API_KEY")).not.toBeVisible();
  });
});

test.describe("Mocked e2e: error and empty states", () => {
  test("AI unavailable shows an error, not fabricated results", async ({
    page,
  }) => {
    // Intercept the analysis POST to return 503 (AI unavailable).
    await page.route(
      `**/api/v1/projects/${PROJECT_ID}/analysis`,
      async (route) => {
        if (route.request().method() === "POST") {
          await route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({
              error: "ai_service_unavailable",
              detail: "AI service is not configured.",
            }),
          });
        } else {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify([]),
          });
        }
      }
    );
    await page.goto(`/projects/${PROJECT_ID}/architecture`);
    await page.click("text=Run analysis");
    // The error is surfaced; no fabricated results are shown.
    await expect(
      page.getByText(/ai_service_unavailable|not configured/i)
    ).toBeVisible();
  });

  test("empty analysis state prompts to run analysis", async ({ page }) => {
    await page.route(
      `**/api/v1/projects/${PROJECT_ID}/analysis`,
      async (route) => {
        if (route.request().method() === "POST") {
          await route.fulfill({
            status: 202,
            contentType: "application/json",
            body: JSON.stringify({ run: { id: "run-1", status: "completed" }, result: null }),
          });
        } else {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify([]),
          });
        }
      }
    );
    await page.goto(`/projects/${PROJECT_ID}/architecture`);
    // Empty state is shown (the "No analysis yet" message).
    await expect(page.getByText(/No analysis yet/i)).toBeVisible();
  });
});
