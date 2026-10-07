import enMessages from "./locales/en.json";
import zhCnMessages from "./locales/zh-CN.json";

export const supportedLocales = ["en", "zh-CN"] as const;

export type Locale = (typeof supportedLocales)[number];
export type TranslationParams = Record<string, string | number>;
export type TFunction = (
  key: string,
  paramsOrFallback?: TranslationParams | string,
  fallback?: string,
) => string;

export type TranslationTree = {
  [key: string]: string | TranslationTree;
};

export type I18nResources = Partial<Record<Locale, TranslationTree>>;

export const defaultLocale: Locale = "en";

const localeMessages: Record<Locale, TranslationTree> = {
  en: enMessages,
  "zh-CN": zhCnMessages,
};

const localeLabels: Record<Locale, string> = {
  en: "English",
  "zh-CN": "简体中文",
};

export function isSupportedLocale(locale: string): locale is Locale {
  return supportedLocales.includes(locale as Locale);
}

export function normalizeLocale(locale: string | null | undefined): Locale {
  if (!locale) {
    return defaultLocale;
  }

  if (isSupportedLocale(locale)) {
    return locale;
  }

  const normalized = locale.replace("_", "-").toLowerCase();
  if (normalized.startsWith("zh")) {
    return "zh-CN";
  }
  if (normalized.startsWith("en")) {
    return "en";
  }

  return defaultLocale;
}

export function getLocaleLabel(locale: Locale) {
  return localeLabels[locale];
}

export function translate(
  locale: Locale,
  key: string,
  paramsOrFallback?: TranslationParams | string,
  fallback?: string,
  resources?: I18nResources,
) {
  const params = typeof paramsOrFallback === "string" ? undefined : paramsOrFallback;
  const explicitFallback = typeof paramsOrFallback === "string" ? paramsOrFallback : fallback;
  const value =
    findMessage(getMessages(locale, resources), key) ??
    (locale === defaultLocale
      ? undefined
      : findMessage(getMessages(defaultLocale, resources), key)) ??
    explicitFallback ??
    key;

  return interpolate(value, params);
}

export function createTranslator(locale: Locale, resources?: I18nResources): TFunction {
  return (key, paramsOrFallback, fallback) =>
    translate(locale, key, paramsOrFallback, fallback, resources);
}

function getMessages(locale: Locale, resources: I18nResources | undefined) {
  const additionalMessages = resources?.[locale];
  return additionalMessages
    ? mergeTranslationTrees(localeMessages[locale], additionalMessages)
    : localeMessages[locale];
}

function mergeTranslationTrees(
  base: TranslationTree,
  overrides: TranslationTree,
): TranslationTree {
  const merged: TranslationTree = { ...base };

  for (const [key, override] of Object.entries(overrides)) {
    const current = merged[key];
    merged[key] =
      typeof current === "object" && typeof override === "object"
        ? mergeTranslationTrees(current, override)
        : override;
  }

  return merged;
}

function findMessage(messages: TranslationTree, key: string) {
  let current: string | TranslationTree | undefined = messages;

  for (const segment of key.split(".")) {
    if (!current || typeof current === "string") {
      return undefined;
    }
    current = current[segment];
  }

  return typeof current === "string" ? current : undefined;
}

function interpolate(message: string, params: TranslationParams | undefined) {
  if (!params) {
    return message;
  }

  return message.replace(/\{(\w+)\}/g, (match, key) =>
    Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match,
  );
}
