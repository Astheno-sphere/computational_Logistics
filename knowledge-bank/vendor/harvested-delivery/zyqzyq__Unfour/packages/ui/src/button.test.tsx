// @vitest-environment jsdom
import { createRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Button } from "./button";

afterEach(cleanup);

describe("Button", () => {
  it("renders a native button with its children by default", () => {
    render(<Button>Send</Button>);

    const button = screen.getByRole("button", { name: "Send" });
    expect(button.tagName).toBe("BUTTON");
  });

  it("fires onClick and respects the disabled state", () => {
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick}>Run</Button>);

    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(onClick).toHaveBeenCalledTimes(1);

    rerender(
      <Button disabled onClick={onClick}>
        Run
      </Button>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
  });

  it("merges caller className with the variant classes", () => {
    render(
      <Button className="custom-class" variant="danger">
        Delete
      </Button>,
    );

    expect(screen.getByRole("button", { name: "Delete" })).toHaveClass(
      "custom-class",
    );
  });

  it("renders the child element instead of a button when asChild is set", () => {
    render(
      <Button asChild>
        <a href="https://example.com">Open</a>
      </Button>,
    );

    const link = screen.getByRole("link", { name: "Open" });
    expect(link.tagName).toBe("A");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("forwards the ref to the underlying button element", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Ref</Button>);

    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });
});
