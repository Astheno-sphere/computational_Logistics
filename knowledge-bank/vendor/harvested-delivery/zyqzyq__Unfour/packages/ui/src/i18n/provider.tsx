import * as React from "react";
import { I18nContext, type I18nContextValue } from "./context";
import {
  createTranslator,
  isSupportedLocale,
  normalizeLocale,
  supportedLocales,
  type I18nResources,
  type Locale,
} from "./messages";

export function I18nProvider({
  children,
  initialLocale,
  resources,
  storageKey = "unfour.locale",
}: {
  children: React.ReactNode;
  initialLocale?: Locale;
  resources?: I18nResources;
  storageKey?: string;
}) {
  const [locale, setLocaleState] = React.useState<Locale>(
    () => initialLocale ?? readStoredLocale(storageKey) ?? getBrowserLocale(),
  );
  const setLocale = React.useCallback(
    (nextLocale: Locale) => {
      setLocaleState(nextLocale);
      writeStoredLocale(storageKey, nextLocale);
    },
    [storageKey],
  );
  const t = React.useMemo(
    () => createTranslator(locale, resources),
    [locale, resources],
  );
  const value = React.useMemo<I18nContextValue>(
    () => ({
      locale,
      locales: supportedLocales,
      setLocale,
      t,
    }),
    [locale, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

function readStoredLocale(storageKey: string) {
  try {
    const stored = globalThis.localStorage?.getItem(storageKey);
    return stored && isSupportedLocale(stored) ? stored : null;
  } catch {
    return null;
  }
}

function writeStoredLocale(storageKey: string, locale: Locale) {
  try {
    globalThis.localStorage?.setItem(storageKey, locale);
  } catch {
    // Ignore storage failures; locale still updates for the current session.
  }
}

function getBrowserLocale() {
  return normalizeLocale(globalThis.navigator?.language);
}
