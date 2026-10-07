// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { EmptyState, ErrorState, LoadingState } from "./states";
import { I18nProvider } from "./i18n";

afterEach(cleanup);

function withI18n(node: ReactNode) {
  return <I18nProvider initialLocale="en">{node}</I18nProvider>;
}

describe("state components", () => {
  it("renders EmptyState content", () => {
    render(<EmptyState>No requests yet</EmptyState>);
    expect(screen.getByText("No requests yet")).toBeInTheDocument();
  });

  it("renders ErrorState content", () => {
    render(<ErrorState>Request failed</ErrorState>);
    expect(screen.getByText("Request failed")).toBeInTheDocument();
  });

  it("falls back to the localized loading label when LoadingState has no children", () => {
    render(withI18n(<LoadingState />));
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("prefers explicit children over the default label", () => {
    render(withI18n(<LoadingState>Fetching schema</LoadingState>));
    expect(screen.getByText("Fetching schema")).toBeInTheDocument();
    expect(screen.queryByText("Loading...")).toBeNull();
  });
});
