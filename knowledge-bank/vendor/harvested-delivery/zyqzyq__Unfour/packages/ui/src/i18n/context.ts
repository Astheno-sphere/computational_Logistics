import * as React from "react";
import {
  createTranslator,
  defaultLocale,
  supportedLocales,
  type Locale,
  type TFunction,
} from "./messages";

export type I18nContextValue = {
  locale: Locale;
  locales: readonly Locale[];
  setLocale: (locale: Locale) => void;
  t: TFunction;
};

export const I18nContext = React.createContext<I18nContextValue>({
  locale: defaultLocale,
  locales: supportedLocales,
  setLocale: () => undefined,
  t: createTranslator(defaultLocale),
});

export function useI18n() {
  return React.useContext(I18nContext);
}

export function useT() {
  return useI18n().t;
}
