<script setup>
// T-614 — sign in / create account. One component, two modes: the fields are
// almost identical and two files would drift apart.
import { computed, ref } from 'vue'
import { login, register } from '../api.js'
import { setSession } from '../lib/auth.js'
import ThemeToggle from './ThemeToggle.vue'

const emit = defineEmits(['authed'])

const mode = ref('login') // 'login' | 'register'
const email = ref('')
const password = ref('')
const displayName = ref('')
const busy = ref(false)
const error = ref('')

const isRegister = computed(() => mode.value === 'register')

// Mirrors the server: db.users.MIN_PASSWORD_LEN is 8, and bcrypt's own 72-byte
// cap is why the server rejects longer ones rather than truncating silently.
const tooShort = computed(
  () => isRegister.value && password.value.length > 0 && password.value.length < 8,
)
const canSubmit = computed(
  () => email.value.includes('@') && password.value.length > 0
    && !(isRegister.value && password.value.length < 8) && !busy.value,
)

function swap() {
  mode.value = isRegister.value ? 'login' : 'register'
  error.value = ''
}

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  try {
    const out = isRegister.value
      ? await register(email.value, password.value, displayName.value)
      : await login(email.value, password.value)
    setSession(out.token, out.user)
    emit('authed', out.user)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

/** Fills the saved account in with one click. Typing an address and password
 *  under time pressure in front of an audience is a needless way to fail. */
function fillSavedAccount() {
  mode.value = 'login'
  email.value = 'demo_account@gmail.com'
  password.value = 'Karan*123'
  error.value = ''
}
</script>

<template>
  <div class="grid min-h-screen place-items-center px-5 py-10">
    <div class="absolute right-4 top-4"><ThemeToggle /></div>

    <div class="w-full max-w-[24rem]">
      <div class="mb-7 text-center">
        <h1 class="text-2xl font-semibold tracking-tight">ResearchGPT</h1>
        <p class="mt-1.5 text-[0.86rem] text-ink-dim dark:text-night-dim">
          Verified literature review, one question at a time.
        </p>
      </div>

      <form class="rounded-2xl border border-paper-line bg-paper-card p-6
                   dark:border-night-line dark:bg-night-card"
            @submit.prevent="submit">
        <h2 class="text-[1.05rem] font-semibold">
          {{ isRegister ? 'Create your account' : 'Sign in' }}
        </h2>

        <label v-if="isRegister" class="mt-5 block">
          <span class="lbl">Name <span class="text-ink-faint">(optional)</span></span>
          <input v-model="displayName" type="text" autocomplete="name"
                 class="fld" placeholder="Abrarullah" />
        </label>

        <label class="mt-4 block">
          <span class="lbl">Email</span>
          <input v-model="email" type="email" autocomplete="email" required
                 class="fld" placeholder="you@example.com" />
        </label>

        <label class="mt-4 block">
          <span class="lbl">Password</span>
          <input v-model="password" type="password" required
                 :autocomplete="isRegister ? 'new-password' : 'current-password'"
                 class="fld" placeholder="••••••••" />
          <span v-if="tooShort" class="mt-1.5 block text-[0.76rem] text-amber-600
                                       dark:text-amber-400">
            At least 8 characters.
          </span>
        </label>

        <p v-if="error"
           class="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2
                  text-[0.8rem] text-rose-700 dark:border-rose-900
                  dark:bg-rose-950/40 dark:text-rose-300">
          {{ error }}
        </p>

        <button type="submit" :disabled="!canSubmit"
                class="btn-primary mt-5 w-full !py-2.5 disabled:opacity-50">
          {{ busy ? 'Working…' : (isRegister ? 'Create account' : 'Sign in') }}
        </button>

        <p class="mt-4 text-center text-[0.82rem] text-ink-dim dark:text-night-dim">
          {{ isRegister ? 'Already have an account?' : 'No account yet?' }}
          <button type="button" class="link font-medium" @click="swap">
            {{ isRegister ? 'Sign in' : 'Create one' }}
          </button>
        </p>
      </form>

      <button type="button"
              class="mt-4 w-full rounded-xl border border-dashed border-paper-line
                     px-4 py-2.5 text-[0.82rem] text-ink-dim transition
                     hover:border-accent hover:text-accent
                     dark:border-night-line dark:text-night-dim"
              @click="fillSavedAccount">
        Use the saved account
      </button>
    </div>
  </div>
</template>

<style scoped>
.lbl {
  @apply mb-1.5 block text-[0.8rem] font-medium text-ink-dim dark:text-night-dim;
}
.fld {
  @apply w-full rounded-lg border border-paper-line bg-paper px-3 py-2 text-[0.9rem]
         outline-none transition focus:border-accent
         dark:border-night-line dark:bg-night dark:text-night-fg;
}
</style>
