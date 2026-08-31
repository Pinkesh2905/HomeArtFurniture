/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./templates/**/*.html",
    "./**/templates/**/*.html",
    "./**/*.py",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Walnut Showroom Palette
        walnut: {
          DEFAULT: "#3B2820",
          50: "#f7f5f3",
          100: "#ede7e3",
          200: "#d9cec5",
          300: "#beada0",
          400: "#9e8777",
          500: "#7d6455",
          600: "#5c473b",
          700: "#49362c",
          800: "#3B2820",
          900: "#2a1b15",
        },
        espresso: {
          DEFAULT: "#5C3D2E",
          hover: "#4a3023",
          light: "#7a5340",
        },
        linen: {
          DEFAULT: "#F5F0E8",
          dark: "#eae3d6",
          light: "#faf7f2",
        },
        parchment: {
          DEFAULT: "#FFFDF7",
          border: "#ece5d8",
        },
        brass: {
          DEFAULT: "#A0845E",
          hover: "#8c724e",
          light: "#ba9f77",
          dark: "#796243",
        },
        charcoal: {
          DEFAULT: "#2C2421",
          muted: "#665a55",
          light: "#8a7d77",
        },
        // Functional Status Colors (Desaturated)
        status: {
          success: "#3D8B5E",
          warning: "#C48B32",
          error: "#B44432",
          info: "#4A7A96",
        },
        // Theme Aliases for compatibility
        primary: "#3B2820",
        "primary-dark": "#2a1b15",
        secondary: "#A0845E",
        "secondary-dark": "#8c724e",
        surface: "#FFFDF7",
        background: "#F5F0E8",
        "on-surface": "#2C2421",
        "on-background": "#2C2421",
        outline: "#D8CFC4",
        error: "#B44432",
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "sm": "0.125rem",
        "md": "0.375rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "2xl": "1rem",
        "full": "9999px"
      },
      spacing: {
        "xl": "48px",
        "lg": "32px",
        "xs": "4px",
        "base": "8px",
        "md": "20px",
        "container-max": "1440px",
        "gutter": "20px",
        "sm": "10px",
        "input": "38px",
        "input-py": "6px",
        "input-px": "12px",
        "panel": "20px",
        "card": "16px",
      },
      fontFamily: {
        "sans": ["DM Sans", "Inter", "ui-sans-serif", "system-ui"],
        "serif": ["DM Serif Display", "serif"],
        "mono": ["JetBrains Mono", "monospace"],
        "tabular": ["JetBrains Mono", "monospace"],
        "h1": ["DM Serif Display", "serif"],
        "h2": ["DM Serif Display", "serif"],
        "h3": ["DM Sans", "ui-sans-serif"],
        "headline-lg": ["DM Serif Display", "serif"],
        "headline-md": ["DM Sans", "ui-sans-serif"],
        "body-lg": ["DM Sans", "ui-sans-serif"],
        "body-base": ["DM Sans", "ui-sans-serif"],
        "body-md": ["DM Sans", "ui-sans-serif"],
        "body-sm": ["DM Sans", "ui-sans-serif"],
        "label-caps": ["DM Sans", "ui-sans-serif"],
        "label-sm": ["DM Sans", "ui-sans-serif"],
        "invoice-accent": ["JetBrains Mono", "monospace"]
      },
      fontSize: {
        "headline-lg": ["32px", { lineHeight: "1.1", fontWeight: "700" }],
        "label-caps": ["12px", { lineHeight: "1", letterSpacing: "0.05em", fontWeight: "700" }],
        "headline-md": ["24px", { lineHeight: "1.3", fontWeight: "600" }],
        "body-base": ["16px", { lineHeight: "1.5", fontWeight: "400" }],
        "body-sm": ["14px", { lineHeight: "1.4", fontWeight: "400" }],
        "invoice-accent": ["18px", { lineHeight: "1.2", fontWeight: "500" }]
      }
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/container-queries")
  ],
};
