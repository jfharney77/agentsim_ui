/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Dell Support runs on Roboto; no serif (or serif-flavored mono) anywhere.
        sans: ["Roboto", "Helvetica Neue", "Segoe UI", "Arial", "sans-serif"],
        // True monospace is reserved for functional text (logs, raw ids).
        mono: ["ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      colors: {
        // Brand / Dell
        dell: {
          DEFAULT: "#0076CE",
          deep: "#005BA1",
          link: "#3B9BEA",
          soft: "#7fb8e8",
        },
        // Dark theme surfaces
        ink: {
          bg: "#0A1727",
          panel: "#10233C",
          panel2: "#0D1E33",
          navlo: "#0C1D31",
        },
        // Light band / cards
        band: "#f4f6f9",
        // Agent-state colors (tweakable)
        state: {
          running: "#F2A81E",
          completed: "#18A673",
          errored: "#E23D3D",
          done: "#37c592",
        },
      },
      boxShadow: {
        frame: "0 24px 60px rgba(6,16,30,.4)",
        "light-card": "0 2px 12px rgba(30,50,80,.06)",
        ask: "0 14px 44px rgba(0,0,0,.38)",
      },
    },
  },
  plugins: [],
}
