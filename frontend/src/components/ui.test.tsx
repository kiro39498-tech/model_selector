import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "../components/ui";

describe("Button", () => {
  it("renders its label", () => {
    render(<Button>Start discovery</Button>);
    expect(screen.getByText("Start discovery")).toBeInTheDocument();
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>Start</Button>);
    expect(screen.getByText("Start")).toBeDisabled();
  });
});
