/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './views/**/*.{js,ts,jsx,tsx,mdx}', // Scan new views directory
    './lib/**/*.{js,ts,jsx,tsx}',        // Theme constants (palette classes)
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
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
        // Custom palette
        ink: {
          DEFAULT: '#001524',
          50: '#a0d7ff',
          100: '#a0d7ff',
          200: '#41b0ff',
          300: '#0083e1',
          400: '#004c83',
          500: '#001524',
          600: '#00111d',
          700: '#000c15',
          800: '#00080e',
          900: '#000407',
          950: '#000204',
        },
        teal: {
          DEFAULT: '#15616d',
          50: '#bfecf3',
          100: '#bfecf3',
          200: '#7ed9e7',
          300: '#3ec5da',
          400: '#2199ab',
          500: '#15616d',
          600: '#104c56',
          700: '#0c3940',
          800: '#08262b',
          900: '#041315',
          950: '#020a0b',
        },
        papaya: {
          DEFAULT: '#ffecd1',
          50: '#fffbf6',
          100: '#fff7ed',
          200: '#fff4e3',
          300: '#fff0da',
          400: '#ffecd1',
          500: '#ffc574',
          600: '#ff9f17',
          700: '#ba6c00',
          800: '#5d3600',
          900: '#2e1b00',
          950: '#170e00',
        },
        tangerine: {
          DEFAULT: '#ff7d00',
          50: '#ffe5cc',
          100: '#ffca99',
          200: '#ffb066',
          300: '#ff9633',
          400: '#ff7d00',
          500: '#cc6300',
          600: '#994a00',
          700: '#663100',
          800: '#331900',
          900: '#1a0c00',
          950: '#0d0600',
        },
        brandy: {
          DEFAULT: '#78290f',
          50: '#f7cbbc',
          100: '#ee9679',
          200: '#e66235',
          300: '#b93f17',
          400: '#78290f',
          500: '#5e200c',
          600: '#471809',
          700: '#2f1006',
          800: '#180803',
          900: '#0c0402',
          950: '#060201',
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: 0 },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: 0 },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
      typography: {
        DEFAULT: {
          css: {
            '--tw-prose-body': '#001524',          // ink
            '--tw-prose-headings': '#001524',      // ink
            '--tw-prose-lead': '#104c56',          // teal-600
            '--tw-prose-links': '#15616d',         // teal
            '--tw-prose-bold': '#001524',          // ink
            '--tw-prose-counters': '#15616d',      // teal
            '--tw-prose-bullets': '#15616d',       // teal
            '--tw-prose-hr': '#ffecd1',            // papaya
            '--tw-prose-quotes': '#001524',        // ink
            '--tw-prose-quote-borders': '#15616d', // teal
            '--tw-prose-captions': '#104c56',      // teal-600
            '--tw-prose-code': '#001524',          // ink
            '--tw-prose-pre-code': '#ffecd1',      // papaya (light text on dark bg)
            '--tw-prose-pre-bg': '#001524',        // ink (dark terminal bg)
            '--tw-prose-th-borders': '#ffecd1',    // papaya
            '--tw-prose-td-borders': '#ffecd1',    // papaya
          },
        },
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
    require('@tailwindcss/typography'),
  ],
}


