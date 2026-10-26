/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Restrained palette per spec.
        surface: "#ffffff",
        canvas: "#faf9f7", // warm off-white
        ink: "#1f2328", // dark charcoal
        muted: "#6b7280",
        accent: {
          DEFAULT: "#4f46e5", // muted indigo
          soft: "#eef2ff",
        },
        border: "#e5e7eb",
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
