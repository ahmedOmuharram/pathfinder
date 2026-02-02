import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Deep ocean theme
        ocean: {
          50: "#e6f4f8",
          100: "#c0e4ed",
          200: "#96d3e2",
          300: "#6bc1d6",
          400: "#4bb4ce",
          500: "#2ba7c5",
          600: "#2596b3",
          700: "#1d8299",
          800: "#166e80",
          900: "#0a4d58",
          950: "#052f36",
        },
        // Coral accent
        coral: {
          50: "#fff5f2",
          100: "#ffe6df",
          200: "#ffc9b8",
          300: "#ffa085",
          400: "#ff7a5c",
          500: "#ff5733",
          600: "#ed3a15",
          700: "#c72d0e",
          800: "#a02612",
          900: "#842315",
        },
        // Neutral tones
        slate: {
          850: "#172033",
          950: "#0a0f1a",
        },
      },
      fontFamily: {
        sans: ["var(--font-display)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "ocean-gradient": "linear-gradient(135deg, #0a4d58 0%, #052f36 50%, #0a0f1a 100%)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;

