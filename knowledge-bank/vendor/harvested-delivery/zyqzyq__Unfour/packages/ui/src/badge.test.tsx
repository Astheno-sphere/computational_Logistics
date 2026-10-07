// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { Badge } from "./badge";

afterEach(cleanup);

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("applies the neutral tone classes by default", () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText("Default").className).toContain(
      "u-badge-neutral-bg",
    );
  });

  it("switches tone classes when a tone is provided", () => {
    render(<Badge tone="green">Online</Badge>);
    const badge = screen.getByText("Online");
    expect(badge.className).toContain("u-badge-success-bg");
    expect(badge.className).not.toContain("u-badge-neutral-bg");
  });

  it("keeps caller className alongside the tone classes", () => {
    render(
      <Badge className="extra" tone="red">
        Error
      </Badge>,
    );
    expect(screen.getByText("Error")).toHaveClass("extra");
  });
});
