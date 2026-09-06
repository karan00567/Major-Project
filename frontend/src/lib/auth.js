// T-614 — who is signed in, and the token that proves it.
//
// One module-level `ref` rather than Pinia: T-604's "a store is ceremony" still
// holds at this size, and every view needs the same two values.
//
// ⚠️ The token lives in localStorage, which is readable by any script running on
// this origin — i.e. it is not XSS-proof. An httpOnly cookie would be, but it
// cannot be read by EventSource's URL either, and this is a localhost demo tool.
// Stated rather than hidden: if this were ever deployed, this is the line to
// revisit first.
import { ref } from 'vue'

const TOKEN_KEY = 'researchgpt.token'
const USER_KEY = 'researchgpt.user'

export const token = ref(localStorage.getItem(TOKEN_KEY) || '')
export const user = ref(readUser())

function readUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null // a corrupt entry is a signed-out user, not a crash on boot
  }
}

export const isAuthed = () => Boolean(token.value)

export function setSession(newToken, newUser) {
  token.value = newToken
  user.value = newUser
  localStorage.setItem(TOKEN_KEY, newToken)
  localStorage.setItem(USER_KEY, JSON.stringify(newUser))
}

export function setUser(newUser) {
  user.value = newUser
  localStorage.setItem(USER_KEY, JSON.stringify(newUser))
}

export function clearSession() {
  token.value = ''
  user.value = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

/** The label shown in the sidebar: a display name if set, else the local part
 *  of the email — never the full address, which overflows a narrow rail. */
export function shortName(u) {
  if (!u) return ''
  return u.display_name || (u.email || '').split('@')[0]
}

export function initials(u) {
  const n = shortName(u)
  if (!n) return '?'
  const parts = n.trim().split(/[\s._-]+/).filter(Boolean)
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : n.slice(0, 2)
  return letters.toUpperCase()
}
