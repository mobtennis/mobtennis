import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Light, sunny, summer palette — Wimbledon whites + grass-court greens.
        // Token names kept (`ink-*`) so components don't need to change; values
        // are now lights instead of darks. Higher number = darker / more elevated
        // contrast (background 950 = lightest cream; border 700 = warmest gray).
        ink: {
          950: "#FAF7F0",   // page background — soft cream
          900: "#FFFFFF",   // card surface — pure white
          800: "#F5F1E6",   // elevated / hover background — warmer cream
          700: "#E5DDC8",   // border / divider — warm sand
          600: "#D6CBAE",   // hover border / stronger divider
        },
        text: {
          primary: "#1F2A37",   // deep charcoal — readable, not pure black
          secondary: "#5C6473", // warm gray
          muted: "#8E96A6",     // softer secondary
        },
        court: {
          grass: "#3FAA5E",     // bright grass green
          clay: "#C2410C",      // terracotta
          hard: "#2563EB",      // sky court blue
          carpet: "#7B5BC4",    // lavender
        },
        accent: {
          DEFAULT: "#16A34A",   // primary accent — grass green
          dim: "#15803D",       // hover / muted state
          warm: "#F59E0B",      // sun-yellow highlight
        },
        live: "#E11D48",        // coral red — live dot
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Inter", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["SF Mono", "ui-monospace", "Menlo", "monospace"],
      },
      borderRadius: { xs: "4px", sm: "6px", md: "10px", lg: "14px" },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,0.6) inset, 0 1px 2px rgba(31,42,55,0.04), 0 4px 12px rgba(31,42,55,0.06)",
      },
      keyframes: {
        livePulse: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.55", transform: "scale(0.85)" },
        },
      },
      animation: { livePulse: "livePulse 1.4s ease-in-out infinite" },
    },
  },
  plugins: [],
};

export default config;
