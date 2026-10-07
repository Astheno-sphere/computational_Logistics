// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CommandPaletteAction } from "./utils";

afterEach(cleanup);

describe("CommandPaletteAction", () => {
  it("renders its children inside a button", () => {
    render(<CommandPaletteAction onSelect={() => {}}>New request</CommandPaletteAction>);
    expect(screen.getByRole("button", { name: "New request" })).toBeInTheDocument();
  });

  it("invokes onSelect when clicked", () => {
    const onSelect = vi.fn();
    render(<CommandPaletteAction onSelect={onSelect}>Run</CommandPaletteAction>);

    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
