<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { login } from "../api/client";

const route = useRoute();
const router = useRouter();

const email = ref("");
const password = ref("");
const error = ref<string | null>(null);
const submitting = ref(false);

async function submit() {
  submitting.value = true;
  error.value = null;
  try {
    await login(email.value.trim(), password.value);
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/inbox";
    await router.push(redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : "/inbox");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo ingresar";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="login">
    <form class="login__card" @submit.prevent="submit">
      <h1>Conversa</h1>
      <p>Ingreso para administración y consejo.</p>
      <div class="login__form">
        <label>
          Email
          <input v-model="email" type="email" autocomplete="username" required />
        </label>
        <label>
          Contraseña
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn-primary" type="submit" :disabled="submitting">
          {{ submitting ? "Ingresando..." : "Ingresar" }}
        </button>
      </div>
    </form>
  </main>
</template>
