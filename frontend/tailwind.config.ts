import type { Config } from "tailwindcss";

// Lighthouse Canton — DCMS-aligned light mode.
// Brand: Agile Red #E50025 · Smart Black #000000 · Bright White #FFFFFF · Warm Grey #CCC6BE.
// Surfaces are white / white-smoke / light greys; text is black / dim-grey on white.
//
// Ink scale convention: HIGHER number = DARKER. Low numbers are surface tints,
// high numbers are text shades. This flips the previous dark-mode scale, so
// existing class usages need a one-time sweep (text-ink-100 → text-ink-900 etc.)
// alongside this token change. The legacy scale keys are preserved so partial
// rollback is possible without restructuring TSX.

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        lc: {
          red: "#E50025",
          "red-dark": "#e41e28", // firebrand-red, hover partner
          black: "#000000",
          white: "#FFFFFF",
          grey: "#CCC6BE", // silver / warm grey
        },
        // App-shell off-white. Body bg uses this so cards (#fff) sit on a
        // subtly tinted surface — DCMS pattern.
        smoke: "#f6f5f3",

        // Neutral scale — natural light-to-dark axis. ink-50 is barely-grey,
        // ink-900 is pure black. Use bg-ink-50/100 for surfaces, ink-200/300
        // for borders, ink-500/600 for body text, ink-900 for headings.
        ink: {
          50: "#fafafa",   // grey-50 — almost-white card / hover bg
          100: "#f4f4f4",  // grey-100 — subtle bg / row hover
          200: "#e5e5e5",  // grey-200 — default border
          300: "#d4d4d4",  // grey-300 — strong border / faint text
          400: "#9a9a9a",  // grey-500 — secondary text / placeholder
          500: "#6c6c6c",  // dim-grey — body text
          600: "#585858",  // dim-grey-2 — strong muted text
          650: "#4d4d4d",  // intermediate (used by some chrome)
          700: "#333333",  // black-80 — heading-secondary
          750: "#1f1f1f",  // intermediate
          800: "#150104",  // brown — deep ink
          850: "#0a0a0a",  // intermediate
          900: "#000000",  // black — primary text/heading
          950: "#000000",  // alias
        },

        // Crimson opacity scale — accent only. Never use brass-400/500/600 as
        // a solid button fill; they're for hover tints, dot accents, focus rings.
        brass: {
          300: "rgba(229, 0, 37, 0.30)",
          400: "#E50025",
          500: "#E50025",
          600: "#E50025",
          700: "rgba(229, 0, 37, 0.60)",
          800: "rgba(229, 0, 37, 0.20)",
          900: "rgba(229, 0, 37, 0.10)",
        },

        // Status — semantic, low-saturation palette deliberately distinct from
        // brand crimson. Used for active/inactive/pending/breach status pills
        // so red still means risk, not brand.
        jade: {
          // OK / Active — muted green
          500: "#0b6b3a",
          600: "#cdeadb",
          700: "#f3fbf6",
        },
        ember: {
          // Breach / Error — muted red, NOT brand crimson
          500: "#8a1b1b",
          600: "#f6c9c9",
          700: "#fdecec",
        },
        amber: {
          // Watch / Warning — kept as Tailwind's amber for compatibility with
          // existing usage; LC has no canonical warning colour.
          400: "#f3dca3",
          500: "#7a5400",
          600: "#fef7e6",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "ui-serif", "Georgia", "serif"],
        sans: [
          "var(--font-sans)",
          "Arial",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        "inner-line": "inset 0 1px 0 0 rgba(0, 0, 0, 0.04)",
        "lc-red": "0 6px 24px -10px rgba(229, 0, 37, 0.55)",
        card: "0 1px 2px rgba(0,0,0,0.04), 0 1px 1px rgba(0,0,0,0.03)",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 0.35s ease-out",
        "pulse-soft": "pulse-soft 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
