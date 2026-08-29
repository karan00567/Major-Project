/** T-614 — Tailwind. Design tokens live here so components use names, not hexes.
 *
 * darkMode 'media' keeps the behaviour the app already had: it follows the
 * operating system rather than offering a toggle. There is no theme switcher to
 * build and no preference to persist.
 */
export default {
  darkMode: 'media',
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        // One accent, used for anything the system is asking you to act on.
        accent: {
          DEFAULT: '#2f6fed',
          hover: '#2560d8',
          soft: '#2f6fed14',
        },
        // The Critic's vocabulary. These are semantic, not decorative: a run's
        // decision chain is the clearest evidence that this is agentic, so the
        // three decisions get three stable colours across the whole app.
        write: '#2f9e5f',
        retrieve: '#2f6fed',
        replan: '#c98a2e',
        // Verdicts.
        supported: '#2f9e5f',
        partial: '#c98a2e',
        unsupported: '#d9534f',
        // Surfaces, light and dark.
        ink: { DEFAULT: '#1a1c1f', dim: '#6b7280' },
        paper: { DEFAULT: '#fbfbfc', card: '#ffffff', line: '#e3e5e9' },
        night: { DEFAULT: '#14161a', card: '#1b1e23', line: '#2a2e35',
                 fg: '#e8eaed', dim: '#9aa1ab' },
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgb(0 0 0 / 0.04), 0 1px 3px rgb(0 0 0 / 0.06)',
        lift: '0 4px 12px rgb(0 0 0 / 0.08), 0 1px 3px rgb(0 0 0 / 0.06)',
      },
      keyframes: {
        pulseRing: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
      },
      animation: { 'pulse-ring': 'pulseRing 1.6s ease-in-out infinite' },
    },
  },
  plugins: [],
}
