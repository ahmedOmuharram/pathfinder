import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Legacy palette kept for gradual migration of graph/domain-specific styles
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
      },
      borderRadius: {
        lg: "calc(var(--radius) + 2px)",
        md: "var(--radius)",
        sm: "calc(var(--radius) - 2px)",
        xl: "calc(var(--radius) + 4px)",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":
          "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "ocean-gradient":
          "linear-gradient(135deg, #0a4d58 0%, #052f36 50%, #0a0f1a 100%)",
      },
      animation: {
        "fade-in": "fade-in var(--duration-normal) var(--ease-default)",
        "fade-out": "fade-out var(--duration-normal) var(--ease-default)",
        "slide-in-from-top":
          "slide-in-from-top var(--duration-normal) var(--ease-spring)",
        "slide-in-from-bottom":
          "slide-in-from-bottom var(--duration-normal) var(--ease-spring)",
        "scale-in": "scale-in var(--duration-normal) var(--ease-spring)",
        "scale-out": "scale-out var(--duration-normal) var(--ease-spring)",
        "accordion-down": "accordion-down var(--duration-slow) var(--ease-spring)",
        "accordion-up": "accordion-up var(--duration-slow) var(--ease-spring)",
        shimmer: "shimmer 2s linear infinite",
        "progress-pulse": "progress-pulse 2s ease-in-out infinite",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "fade-out": {
          from: { opacity: "1" },
          to: { opacity: "0" },
        },
        "slide-in-from-top": {
          from: { transform: "translateY(-4px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        "slide-in-from-bottom": {
          from: { transform: "translateY(4px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        "scale-in": {
          from: { transform: "scale(0.95)", opacity: "0" },
          to: { transform: "scale(1)", opacity: "1" },
        },
        "scale-out": {
          from: { transform: "scale(1)", opacity: "1" },
          to: { transform: "scale(0.95)", opacity: "0" },
        },
        "accordion-down": {
          from: { height: "0", opacity: "0" },
          to: { height: "var(--radix-accordion-content-height)", opacity: "1" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)", opacity: "1" },
          to: { height: "0", opacity: "0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
