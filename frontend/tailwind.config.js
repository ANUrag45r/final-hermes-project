/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Tokens driven by CSS variables so light/dark swap with no class churn.
        ink: {
          DEFAULT: "var(--ink)",
          800: "var(--ink-800)",
          700: "var(--ink-700)",
          600: "var(--ink-600)",
        },
        paper: "var(--paper)",
        surface: "var(--surface)",
        slate: {
          line: "var(--line)",
        },
        // Accents stay constant across themes.
        recall: {
          DEFAULT: "#E8A23D",
          soft: "var(--recall-soft)",
        },
        synapse: "#3A7CA5",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,30,46,0.04), 0 8px 24px -12px rgba(15,30,46,0.12)",
      },
      keyframes: {
        pulseNode: {
          "0%,100%": { opacity: "0.35", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.15)" },
        },
        riseIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        node: "pulseNode 3s ease-in-out infinite",
        rise: "riseIn 0.4s ease-out both",
      },
    },
  },
  plugins: [],
};
