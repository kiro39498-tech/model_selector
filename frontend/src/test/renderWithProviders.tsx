import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement, ReactNode } from "react";

/**
 * Render a component within a QueryClientProvider and a MemoryRouter.
 *
 * `initialData` lets tests seed query results deterministically (mocked data).
 * This is NOT live integration — it is a deterministic mock.
 */
export function renderWithProviders(
  ui: ReactElement,
  options: {
    initialData?: Record<string, unknown>;
    route?: string;
  } = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  // Seed query data by key prefix.
  for (const [key, value] of Object.entries(options.initialData ?? {})) {
    queryClient.setQueryData([key], value);
  }

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[options.route ?? "/"]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return { ...render(ui, { wrapper: Wrapper }), queryClient };
}
