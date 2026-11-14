/**
 * Interface language for the public-facing text: the home page and the five missions (optimisation.md IMP-5).
 * Chosen on the home page, remembered in this browser, and settable by a link (`?lang=hi`). Controls, labels and
 * measurements stay in English: they are the vocabulary of the data and of every other tool.
 */
import { useSyncExternalStore } from "react";

export type Lang = "en" | "hi" | "es";
export const LANGS: { id: Lang; name: string }[] = [
  { id: "en", name: "English" }, { id: "hi", name: "हिन्दी" }, { id: "es", name: "Español" },
];

const KEY = "parallax.lang";
const isLang = (v: unknown): v is Lang => v === "en" || v === "hi" || v === "es";

function initial(): Lang {
  try {
    const fromLink = new URLSearchParams(location.search).get("lang");
    if (isLang(fromLink)) return fromLink;
    const saved = localStorage.getItem(KEY);
    if (isLang(saved)) return saved;
  } catch { /* no storage (private mode, embed): English */ }
  return "en";
}

let current: Lang = initial();
const listeners = new Set<() => void>();

export function getLang(): Lang { return current; }

export function setLang(l: Lang): void {
  current = l;
  try { localStorage.setItem(KEY, l); } catch { /* not remembered */ }
  if (typeof document !== "undefined") document.documentElement.lang = l;
  for (const f of listeners) f();
}

export function useLang(): Lang {
  return useSyncExternalStore((f) => { listeners.add(f); return () => listeners.delete(f); }, getLang, () => "en" as Lang);
}

if (typeof document !== "undefined" && current !== "en") document.documentElement.lang = current;
