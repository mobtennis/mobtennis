/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        // Mirror of web/tailwind.config.ts — keep these in sync.
        ink: {
          950: "#FAF7F0",
          900: "#FFFFFF",
          800: "#F5F1E6",
          700: "#E5DDC8",
          600: "#D6CBAE",
        },
        text: {
          primary: "#1F2A37",
          secondary: "#5C6473",
          muted: "#8E96A6",
        },
        court: {
          grass: "#3FAA5E",
          clay: "#C2410C",
          hard: "#2563EB",
          carpet: "#7B5BC4",
        },
        accent: {
          DEFAULT: "#16A34A",
          dim: "#15803D",
          warm: "#F59E0B",
        },
        live: "#E11D48",
      },
    },
  },
  plugins: [],
};
