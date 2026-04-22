import type { Config } from "tailwindcss";

// Lighthouse Canton brand palette — exactly four colours.
// Agile Red #E50025 · Smart Black #000000 · Bright White #FFFFFF · Warm Grey #CCC6BE.
// Surfaces on black are built with Warm Grey opacities (no additional hues).
// The legacy `ink` / `brass` / `jade` / `ember` token names are kept so existing
// class usages stay valid, but every value now maps to brand palette.

const warmGrey = (alpha: number) => `rgba(204, 198, 190, ${alpha})`;
const agileRed = (alpha: number) => `rgba(229, 0, 37, ${alpha})`;

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
          black: "#000000",
          white: "#FFFFFF",
          grey: "#CCC6BE",
        },
        // Surface scale — warm grey over smart black
        ink: {
          950: "#000000",
          900: warmGrey(0.04),
          850: warmGrey(0.06),
          800: warmGrey(0.09),
          750: warmGrey(0.12),
          700: warmGrey(0.15),
          650: warmGrey(0.2),
          600: warmGrey(0.28),
          500: warmGrey(0.4),
          400: warmGrey(0.55),
          300: warmGrey(0.72),
          200: "#CCC6BE",
          100: "#FFFFFF",
          50: "#FFFFFF",
        },
        // Accent scale — all agile red, varying by opacity for hover/subtle states
        brass: {
          300: agileRed(0.3),
          400: "#E50025",
          500: "#E50025",
          600: "#E50025",
          700: agileRed(0.6),
          800: agileRed(0.2),
          900: agileRed(0.1),
        },
        // "Success / active" has no green in the brand — render as white.
        jade: {
          500: "#FFFFFF",
          600: "rgba(255, 255, 255, 0.9)",
        },
        // Error / destructive — collapses to Agile Red.
        ember: {
          500: "#E50025",
          600: agileRed(0.8),
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
        'inner-line': 'inset 0 1px 0 0 rgba(204, 198, 190, 0.08)',
        'lc-red': '0 6px 24px -10px rgba(229, 0, 37, 0.55)',
      },
      keyframes: {
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.35s ease-out',
        'pulse-soft': 'pulse-soft 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
export default config;
