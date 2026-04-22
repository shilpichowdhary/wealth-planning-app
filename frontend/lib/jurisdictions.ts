// Central jurisdiction registry. Slugs match the `jurisdiction` tag written
// into ChromaDB metadata by the KB ingestion script.

export type JurisdictionSlug =
  | "india"
  | "singapore"
  | "uae"
  | "usa"
  | "uk"
  | "taiwan"
  | "china"
  | "cross-border";

export interface Jurisdiction {
  slug: JurisdictionSlug;
  label: string;
  short: string;
  flag: string;
}

export const JURISDICTIONS: Jurisdiction[] = [
  { slug: "india", label: "India", short: "IN", flag: "🇮🇳" },
  { slug: "singapore", label: "Singapore", short: "SG", flag: "🇸🇬" },
  { slug: "uae", label: "UAE", short: "AE", flag: "🇦🇪" },
  { slug: "usa", label: "USA", short: "US", flag: "🇺🇸" },
  { slug: "uk", label: "UK", short: "UK", flag: "🇬🇧" },
  { slug: "taiwan", label: "Taiwan", short: "TW", flag: "🇹🇼" },
  { slug: "china", label: "China", short: "CN", flag: "🇨🇳" },
  { slug: "cross-border", label: "Cross-border", short: "XB", flag: "🌐" },
];

export const JURISDICTION_BY_SLUG: Record<JurisdictionSlug, Jurisdiction> =
  Object.fromEntries(JURISDICTIONS.map((j) => [j.slug, j])) as Record<
    JurisdictionSlug,
    Jurisdiction
  >;

export function jurisdictionLabel(slug: string): string {
  const j = JURISDICTION_BY_SLUG[slug as JurisdictionSlug];
  return j ? j.label : slug;
}

export function jurisdictionFlag(slug: string): string {
  const j = JURISDICTION_BY_SLUG[slug as JurisdictionSlug];
  return j ? j.flag : "📄";
}
