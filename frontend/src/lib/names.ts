/**
 * A target's name for people. The resolver returns SIMBAD's main identifier, which carries catalogue prefixes:
 * "NAME Barnard's star", "* eps Ind B", "V* R Dra". Shown as is they read like a bug (browser test 2026-11-14), so
 * the prefix is dropped for display; the raw identifier stays in the data, the tooltips and the exports.
 */
const SIMBAD_PREFIX = /^(NAME|V\*|\*\*|\*)\s+/;

export function displayName(t: { name: string; label_hint?: string | null }): string {
  return t.label_hint ?? t.name.replace(SIMBAD_PREFIX, "");
}
