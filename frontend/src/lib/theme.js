// Theme: system (default), light, or dark.
//
// The default is the OS preference, which is exactly what `darkMode: 'media'`
// gave before, so a reader who never touches the control sees no change. The
// override exists because the OS setting is often wrong for the situation the
// page is being read in - a projector, a shared lecture-hall laptop - and that
// is not something you can fix from the podium.
//
// ⚠️ The class must be on <html> BEFORE first paint or the page flashes the
// wrong theme. index.html carries a tiny inline script that does that; this
// module owns the same key and must stay in sync with it.
import { ref } from 'vue'

const KEY = 'researchgpt-theme'
const MODES = ['system', 'light', 'dark']

const media = window.matchMedia('(prefers-color-scheme: dark)')

function stored() {
  try {
    const v = localStorage.getItem(KEY)
    return MODES.includes(v) ? v : 'system'
  } catch {
    return 'system'   // private mode, or storage disabled
  }
}

export const mode = ref(stored())

function paint() {
  const dark = mode.value === 'dark' || (mode.value === 'system' && media.matches)
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

export function setMode(next) {
  if (!MODES.includes(next)) return
  mode.value = next
  try {
    if (next === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, next)
  } catch {
    /* an unwritable store is not a reason to refuse the change this session */
  }
  paint()
}

export function cycleMode() {
  setMode(MODES[(MODES.indexOf(mode.value) + 1) % MODES.length])
}

// Following the OS while in 'system' means reacting to it changing, which it
// does on a schedule on both macOS and Windows.
media.addEventListener('change', () => { if (mode.value === 'system') paint() })

paint()

export { MODES }
