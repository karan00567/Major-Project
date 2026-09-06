<script setup>
// T-614 — update profile. Reachable from the sidebar account button.
//
// Changing an email or a password requires the CURRENT one, enforced server
// side in db.users.update_profile. The field appears only when it is actually
// needed, so a display-name change stays a two-second edit.
import { computed, ref } from 'vue'
import { updateProfile } from '../api.js'
import { setUser, user } from '../lib/auth.js'
import ThemeToggle from './ThemeToggle.vue'

const emit = defineEmits(['close'])

const displayName = ref(user.value?.display_name || '')
const email = ref(user.value?.email || '')
const newPassword = ref('')
const currentPassword = ref('')
const busy = ref(false)
const error = ref('')
const saved = ref('')

const emailChanged = computed(
  () => email.value.trim().toLowerCase() !== (user.value?.email || '').toLowerCase(),
)
const needsCurrent = computed(() => emailChanged.value || newPassword.value.length > 0)
const pwTooShort = computed(
  () => newPassword.value.length > 0 && newPassword.value.length < 8,
)
const canSave = computed(
  () => !busy.value && !pwTooShort.value
    && (!needsCurrent.value || currentPassword.value.length > 0),
)

async function save() {
  if (!canSave.value) return
  busy.value = true
  error.value = ''
  saved.value = ''
  try {
    // Only send what actually changed: a PATCH that echoes every field back
    // would make an unchanged email look like a rename and demand a password.
    const patch = {}
    if (displayName.value !== (user.value?.display_name || '')) {
      patch.display_name = displayName.value
    }
    if (emailChanged.value) patch.email = email.value.trim()
    if (newPassword.value) patch.new_password = newPassword.value
    if (needsCurrent.value) patch.current_password = currentPassword.value

    if (!Object.keys(patch).length) {
      saved.value = 'Nothing to change.'
      return
    }
    setUser(await updateProfile(patch))
    newPassword.value = ''
    currentPassword.value = ''
    saved.value = 'Saved.'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 grid place-items-center bg-black/45 px-4"
       @click.self="emit('close')">
    <div class="w-full max-w-[26rem] rounded-2xl border border-paper-line
                bg-paper-card p-6 shadow-lift dark:border-night-line
                dark:bg-night-card">
      <div class="flex items-start justify-between">
        <div>
          <h2 class="text-[1.05rem] font-semibold">Profile &amp; settings</h2>
          <p class="mt-1 text-[0.79rem] text-ink-faint dark:text-night-faint">
            {{ user?.email }}
          </p>
        </div>
        <button class="rounded-lg p-1.5 text-ink-dim hover:bg-paper-sunk
                       dark:text-night-dim dark:hover:bg-night-sunk"
                aria-label="Close" @click="emit('close')">✕</button>
      </div>

      <label class="mt-5 block">
        <span class="lbl">Display name</span>
        <input v-model="displayName" type="text" class="fld" placeholder="Your name" />
      </label>

      <label class="mt-4 block">
        <span class="lbl">Email</span>
        <input v-model="email" type="email" class="fld" />
      </label>

      <label class="mt-4 block">
        <span class="lbl">New password <span class="text-ink-faint">(optional)</span></span>
        <input v-model="newPassword" type="password" autocomplete="new-password"
               class="fld" placeholder="Leave blank to keep it" />
        <span v-if="pwTooShort" class="mt-1.5 block text-[0.76rem] text-amber-600
                                       dark:text-amber-400">
          At least 8 characters.
        </span>
      </label>

      <label v-if="needsCurrent" class="mt-4 block">
        <span class="lbl">Current password</span>
        <input v-model="currentPassword" type="password"
               autocomplete="current-password" class="fld" />
        <span class="mt-1.5 block text-[0.76rem] text-ink-faint dark:text-night-faint">
          Required to change your email or password.
        </span>
      </label>

      <div class="mt-5 flex items-center justify-between border-t border-paper-line
                  pt-4 dark:border-night-line">
        <span class="text-[0.8rem] text-ink-dim dark:text-night-dim">Theme</span>
        <ThemeToggle />
      </div>

      <p v-if="error"
         class="mt-4 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2
                text-[0.8rem] text-rose-700 dark:border-rose-900
                dark:bg-rose-950/40 dark:text-rose-300">{{ error }}</p>
      <p v-else-if="saved"
         class="mt-4 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2
                text-[0.8rem] text-emerald-700 dark:border-emerald-900
                dark:bg-emerald-950/40 dark:text-emerald-300">{{ saved }}</p>

      <button class="btn-primary mt-5 w-full !py-2.5 disabled:opacity-50"
              :disabled="!canSave" @click="save">
        {{ busy ? 'Saving…' : 'Save changes' }}
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
