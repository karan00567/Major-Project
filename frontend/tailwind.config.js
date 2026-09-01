/** T-614 — Tailwind. Design tokens live here so components use names, not hexes.
 *
 * darkMode is 'class' rather than 'media' (changed 2026-08-30). The old note
 * here said a switcher was ceremony, and for a single demo screen it was. It
 * stopped being true once the app grew a marketing route: a projector and a
 * lecture-hall laptop rarely agree with the OS setting, and "the dashboard is
 * unreadable on the hall's machine" is not a problem you fix from the podium.
 * `useTheme.js` still DEFAULTS to the OS preference, so nothing changes for a
 * reader who never touches the control - it only becomes overridable.
 */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        // One accent, used for anything the system is asking you to act on.
        accent: {
          DEFAULT: '#2f6fed',
          hover: '#2560d8',
          soft: '#2f6fed14',
          lite: '#7ba6ff',       // legible on the night surfaces
        },
        // The Critic's vocabulary. These are semantic, not decorative: a run's
        // decision chain is the clearest evidence that this is agentic, so the
        // three decisions get three stable colours across the whole app.
        write: { DEFAULT: '#2f9e5f', lite: '#5ecb8c' },
        retrieve: { DEFAULT: '#2f6fed', lite: '#7ba6ff' },
        replan: { DEFAULT: '#c98a2e', lite: '#e5b062' },
        // Verdicts. `contradicted` was an inline #8e44ad in PanelDropped; a
        // verdict the UI has a colour for belongs in the vocabulary with the
        // other three, not hardcoded at one call site.
        supported: { DEFAULT: '#2f9e5f', lite: '#5ecb8c' },
        partial: { DEFAULT: '#c98a2e', lite: '#e5b062' },
        unsupported: { DEFAULT: '#d9534f', lite: '#f08a86' },
        contradicted: { DEFAULT: '#8e44ad', lite: '#c08ad8' },
        // Surfaces, light and dark.
        // `faint` is the tertiary tier: run ids, chunk ids, the second copy of
        // something already stated. #9ca3af read at 2.4:1 on the paper ground,
        // which is unreadable rather than quiet; #7d8490 is 3.5:1 and still
        // clearly recessive against `dim` at 4.6:1.
        ink: { DEFAULT: '#1a1c1f', dim: '#6b7280', faint: '#7d8490' },
        paper: { DEFAULT: '#f7f8fa', card: '#ffffff', sunk: '#eff1f5',
                 line: '#e3e5e9', hair: '#eceef2' },
        night: { DEFAULT: '#111317', card: '#1a1d23', sunk: '#15181d',
                 line: '#2a2e35', hair: '#22262c',
                 fg: '#e8eaed', dim: '#9aa1ab', faint: '#6f7681' },
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgb(16 24 40 / 0.04), 0 1px 3px rgb(16 24 40 / 0.06)',
        lift: '0 4px 12px rgb(16 24 40 / 0.08), 0 1px 3px rgb(16 24 40 / 0.06)',
      },
      keyframes: {
        pulseRing: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
        // For skeletons: a run's first paint has nothing in it, and an empty
        // grey box reads as broken where a moving one reads as pending.
        shimmer: {
          '0%': { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
        riseIn: {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'pulse-ring': 'pulseRing 1.6s ease-in-out infinite',
        shimmer: 'shimmer 1.4s linear infinite',
        'rise-in': 'riseIn .28s ease-out both',
      },
    },
  },
  plugins: [],
}
