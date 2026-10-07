import { describe, expect, it } from "vitest";
import {
  createTranslator,
  isSupportedLocale,
  normalizeLocale,
  supportedLocales,
} from "./i18n";

describe("i18n helpers", () => {
  it("keeps the first-stage supported locale list small and stable", () => {
    expect(supportedLocales).toEqual(["en", "zh-CN"]);
    expect(isSupportedLocale("en")).toBe(true);
    expect(isSupportedLocale("zh-CN")).toBe(true);
    expect(isSupportedLocale("ja")).toBe(false);
  });

  it("normalizes browser locale variants to a supported locale", () => {
    expect(normalizeLocale("zh")).toBe("zh-CN");
    expect(normalizeLocale("zh-Hans-CN")).toBe("zh-CN");
    expect(normalizeLocale("en-US")).toBe("en");
    expect(normalizeLocale("fr-FR")).toBe("en");
  });

  it("resolves nested translation keys for each locale", () => {
    expect(createTranslator("en")("app.nav.apiClient")).toBe("API Client");
    expect(createTranslator("zh-CN")("app.nav.database")).toBe("数据库");
  });

  it("falls back to English and then the key for missing translations", () => {
    const t = createTranslator("zh-CN");

    expect(t("common.state.unavailable")).toBe("Unavailable");
    expect(t("missing.translation.key")).toBe("missing.translation.key");
  });
});
