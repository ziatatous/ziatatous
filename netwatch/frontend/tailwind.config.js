/** Design tokens are CSS variables (src/styles.css) and mirrored here. Colours always carry meaning. */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: 'var(--bg-void)', panel: 'var(--bg-panel)', line: 'var(--line)',
        yellow: 'var(--yellow)', red: 'var(--red)', cyan: 'var(--cyan)', green: 'var(--green)', magenta: 'var(--magenta)',
        ink: 'var(--text)', dim: 'var(--text-dim)',
      },
      fontFamily: {
        hud: ['Rajdhani', 'sans-serif'], mono: ['"JetBrains Mono"', 'monospace'],
        body: ['Inter', 'system-ui', 'sans-serif'], big: ['Orbitron', 'Rajdhani', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
