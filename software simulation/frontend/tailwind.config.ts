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
        graphite: {
          900: "#070B12",
          800: "#0D131F",
          700: "#131C2D",
          600: "#1E2B42",
        },
        navy: {
          900: "#0B1528",
          800: "#10203D",
          700: "#172D54",
          600: "#224266",
        },
        rf: {
          cyan: "#00E5FF",
          amber: "#FFB300",
          emerald: "#00E676",
          crimson: "#FF1744",
        }
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Courier New", "monospace"],
      }
    },
  },
  plugins: [],
};

export default config;

