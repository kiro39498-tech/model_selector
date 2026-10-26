import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Welcome from "./Welcome";

vi.mock("../api", () => ({
  api: {
    listProjects: vi.fn(),
    createProject: vi.fn(),
  },
}));

import { api } from "../api";

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Welcome />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Welcome", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listProjects).mockResolvedValue([]);
  });

  it("renders the project creation form", () => {
    renderAt("/");
    expect(screen.getByText("AI Application Architect")).toBeInTheDocument();
    expect(screen.getByLabelText("Project name")).toBeInTheDocument();
    expect(screen.getByLabelText("Describe your application")).toBeInTheDocument();
  });

  it("disables submit until name and description are provided", () => {
    renderAt("/");
    const button = screen.getByRole("button", { name: /start discovery/i });
    expect(button).toBeDisabled();
  });

  it("enables submit and calls createProject when filled", async () => {
    vi.mocked(api.createProject).mockResolvedValue({
      id: "p1",
      name: "Test",
      description: "",
      status: "discovery",
      initial_description: "d",
      created_at: "2026-10-20T00:00:00Z",
    });
    renderAt("/");
    fireEvent.change(screen.getByLabelText("Project name"), {
      target: { value: "Test" },
    });
    fireEvent.change(screen.getByLabelText("Describe your application"), {
      target: { value: "A support assistant" },
    });
    const button = screen.getByRole("button", { name: /start discovery/i });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);
    // The mutation calls createProject; wait for it to be invoked.
    await waitFor(() =>
      expect(api.createProject).toHaveBeenCalledWith(
        "Test",
        "A support assistant"
      )
    );
  });

  it("shows an error state when creation fails", async () => {
    vi.mocked(api.createProject).mockRejectedValue(
      new Error("ai_service_unavailable")
    );
    renderAt("/");
    fireEvent.change(screen.getByLabelText("Project name"), {
      target: { value: "Test" },
    });
    fireEvent.change(screen.getByLabelText("Describe your application"), {
      target: { value: "d" },
    });
    fireEvent.click(screen.getByRole("button", { name: /start discovery/i }));
    // The error is surfaced to the user.
    expect(await screen.findByText("ai_service_unavailable")).toBeInTheDocument();
  });
});
