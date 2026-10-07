<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { fetchMe } from "../api/client";
import { clearSession, getSessionUser, ROLE_LABELS, saveSession, getToken, type SessionUser } from "../api/session";

const router = useRouter();
const user = ref<SessionUser | null>(getSessionUser());

onMounted(async () => {
  if (!getToken()) {
    await router.replace({ name: "login" });
    return;
  }
  try {
    const current = await fetchMe();
    user.value = current;
    const token = getToken();
    if (token) saveSession(token, current);
  } catch {
    clearSession();
    await router.replace({ name: "login" });
  }
});

function logout() {
  clearSession();
  router.push({ name: "login" });
}
</script>

<template>
  <div class="app-frame">
    <header class="app-shell-nav">
      <nav class="app-shell-nav__links">
        <RouterLink class="app-shell-nav__brand" to="/inbox">Conversa</RouterLink>
        <RouterLink class="app-shell-nav__link" to="/inbox">Inbox</RouterLink>
        <RouterLink class="app-shell-nav__link" to="/settings">Settings</RouterLink>
      </nav>
      <div class="app-shell-nav__user">
        <span v-if="user">{{ user.name || user.email }} · {{ ROLE_LABELS[user.role] }}</span>
        <button class="btn-ghost" type="button" @click="logout">Salir</button>
      </div>
    </header>
    <router-view />
  </div>
</template>
