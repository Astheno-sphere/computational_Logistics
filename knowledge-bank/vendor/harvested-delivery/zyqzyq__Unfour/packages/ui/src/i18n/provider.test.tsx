// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { I18nProvider } from "./provider";
import { useI18n } from "./context";
import type { I18nResources } from "./messages";

afterEach(cleanup);
beforeEach(() => globalThis.localStorage?.clear());

function LocaleProbe() {
  const { locale, setLocale, t } = useI18n();
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="nav">{t("app.nav.database")}</span>
      <span data-testid="external">{t("host.greeting", { name: "Ada" })}</span>
      <button onClick={() => setLocale("zh-CN")} type="button">
        zh
      </button>
    </div>
  );
}

const resources: I18nResources = {
  en: {
    host: { greeting: "Hello, {name}", englishOnly: "English host value" },
    app: { nav: { database: "Host Database" } },
  },
  "zh-CN": {
    host: { greeting: "你好，{name}" },
  },
};

describe("I18nProvider", () => {
  it("uses the initialLocale and translates with it", () => {
    render(
      <I18nProvider initialLocale="en">
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("en");
    expect(screen.getByTestId("nav").textContent).toBe("Database");
  });

  it("updates locale and persists it to storage when setLocale runs", () => {
    render(
      <I18nProvider initialLocale="en" storageKey="test.locale">
        <LocaleProbe />
      </I18nProvider>,
    );

    act(() => {
      screen.getByRole("button", { name: "zh" }).click();
    });

    expect(screen.getByTestId("locale").textContent).toBe("zh-CN");
    expect(screen.getByTestId("nav").textContent).toBe("数据库");
    expect(globalThis.localStorage.getItem("test.locale")).toBe("zh-CN");
  });

  it("restores a previously stored locale on mount", () => {
    globalThis.localStorage.setItem("test.locale", "zh-CN");

    render(
      <I18nProvider storageKey="test.locale">
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("zh-CN");
  });

  it("reads external English resources and interpolates parameters", () => {
    render(
      <I18nProvider initialLocale="en" resources={resources}>
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("external").textContent).toBe("Hello, Ada");
  });

  it("reads external Chinese resources and updates them when locale changes", () => {
    render(
      <I18nProvider initialLocale="en" resources={resources}>
        <LocaleProbe />
      </I18nProvider>,
    );

    act(() => screen.getByRole("button", { name: "zh" }).click());

    expect(screen.getByTestId("external").textContent).toBe("你好，Ada");
  });

  it("falls back to external English resources when the current locale is missing a key", () => {
    function FallbackProbe() {
      return <span>{useI18n().t("host.englishOnly")}</span>;
    }

    render(
      <I18nProvider initialLocale="zh-CN" resources={resources}>
        <FallbackProbe />
      </I18nProvider>,
    );

    expect(screen.getByText("English host value")).toBeTruthy();
  });

  it("deep-merges resource branches and lets external leaves override built-ins", () => {
    function MergeProbe() {
      const { t } = useI18n();
      return (
        <div>
          <span>{t("app.nav.apiClient")}</span>
          <span>{t("app.nav.database")}</span>
        </div>
      );
    }

    render(
      <I18nProvider initialLocale="en" resources={resources}>
        <MergeProbe />
      </I18nProvider>,
    );

    expect(screen.getByText("API Client")).toBeTruthy();
    expect(screen.getByText("Host Database")).toBeTruthy();
  });
});
