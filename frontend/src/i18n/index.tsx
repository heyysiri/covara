"use client";

// Site-wide language support.
//  * Static UI text: write the English sentence inside t("..."). Other languages come from translations.json,
//    generated ahead of time with Sarvam (see backend/scripts/gen_i18n.py). A missing entry falls back to English.
//  * Variables: t("{n} of {m} done", { n: 2, m: 5 }).
//  * Text that comes from the backend (findings, actions, explanations): useLocalized([...texts]).

import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";

import { request } from "@/lib/api";

import translations from "./translations.json";

export const LANGUAGES = [
  { code: "en-IN", label: "English" },
  { code: "hi-IN", label: "हिन्दी" },
] as const;

export type LangCode = (typeof LANGUAGES)[number]["code"];
const CODES = new Set<string>(LANGUAGES.map((l) => l.code));
const DICT = translations as Record<string, Record<string, string>>;
const STORAGE_KEY = "covara.lang";

type Vars = Record<string, string | number>;
export type TFn = (text: string, vars?: Vars) => string;

const interpolate = (text: string, vars?: Vars) =>
  vars ? text.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : text;

interface Ctx {
  lang: LangCode;
  setLang: (l: LangCode) => void;
  t: TFn;
}

const I18nContext = createContext<Ctx>({ lang: "en-IN", setLang: () => {}, t: (s, v) => interpolate(s, v) });

// The chosen language lives in a tiny external store (localStorage-backed) so every component re-renders
// together and the first client render matches the server (English) before switching.
let current: LangCode | null = null;
const listeners = new Set<() => void>();

function readLang(): LangCode {
  if (current) return current;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && CODES.has(saved)) current = saved as LangCode;
  } catch {
    /* storage unavailable */
  }
  return current ?? "en-IN";
}

function writeLang(l: LangCode) {
  current = l;
  try {
    localStorage.setItem(STORAGE_KEY, l);
  } catch {
    /* ignore */
  }
  listeners.forEach((f) => f());
}

const subscribeLang = (cb: () => void) => {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
};

export function I18nProvider({ children }: { children: ReactNode }) {
  const lang = useSyncExternalStore(subscribeLang, readLang, () => "en-IN" as LangCode);

  useEffect(() => {
    document.documentElement.lang = lang.split("-")[0];
  }, [lang]);

  const value = useMemo<Ctx>(
    () => ({
      lang,
      setLang: writeLang,
      t: (text, vars) => interpolate(lang === "en-IN" ? text : (DICT[lang]?.[text] ?? text), vars),
    }),
    [lang],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);

export function LanguageSelect({ className = "" }: { className?: string }) {
  const { lang, setLang, t } = useI18n();
  return (
    <select
      aria-label={t("Language")}
      value={lang}
      onChange={(e) => setLang(e.target.value as LangCode)}
      className={`h-8 rounded-md border bg-background px-2 text-sm ${className}`}
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}

// ---- backend-generated text ------------------------------------------------------------------

const dynamicCache = new Map<string, string>();

/** Translate backend-provided strings (amounts, dates and IDs are left unchanged by the server).
 *  Returns the English text until the translation arrives. */
export function useLocalized(texts: string[]): string[] {
  const { lang } = useI18n();
  const key = JSON.stringify(texts);
  const [, bump] = useState(0);

  useEffect(() => {
    if (lang === "en-IN") return;
    const list: string[] = JSON.parse(key);
    const missing = Array.from(new Set(list.filter((x) => x.trim() && !dynamicCache.has(`${lang}|${x}`))));
    if (missing.length === 0) return;
    let cancelled = false;
    (async () => {
      for (let i = 0; i < missing.length; i += 40) {
        const batch = missing.slice(i, i + 40);
        try {
          const res = await request<{ texts: string[]; ok: boolean[] }>("/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texts: batch, lang }),
          });
          batch.forEach((src, j) => dynamicCache.set(`${lang}|${src}`, res.ok[j] ? res.texts[j] : src));
        } catch {
          batch.forEach((src) => dynamicCache.set(`${lang}|${src}`, src)); // keep English, do not retry in a loop
        }
        if (!cancelled) bump((n) => n + 1);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lang, key]);

  return texts.map((x) => (lang === "en-IN" ? x : (dynamicCache.get(`${lang}|${x}`) ?? x)));
}
