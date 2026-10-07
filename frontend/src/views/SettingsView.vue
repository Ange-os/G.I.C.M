<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  type ThemePreference,
  applyTheme,
  getStoredTheme,
  setThemePreference,
} from "../theme";

const route = useRoute();
const router = useRouter();

type Section = "appearance" | "analytics";

const section = computed<Section>(() => {
  const s = route.query.section;
  if (s === "analytics") return "analytics";
  return "appearance";
});

const theme = ref<ThemePreference>(getStoredTheme());

watch(theme, (value) => {
  setThemePreference(value);
});

function go(next: Section) {
  router.replace({ name: "settings", query: { section: next } });
}

function onThemeChange(value: ThemePreference) {
  theme.value = value;
  applyTheme(value);
}
</script>

<template>
  <div class="settings">
    <aside class="settings__nav">
      <h1>Settings</h1>
      <nav>
        <button
          type="button"
          class="settings__nav-item"
          :class="{ active: section === 'appearance' }"
          @click="go('appearance')"
        >
          Appearance
        </button>
        <button
          type="button"
          class="settings__nav-item"
          :class="{ active: section === 'analytics' }"
          @click="go('analytics')"
        >
          Analytics
        </button>
      </nav>
    </aside>

    <main class="settings__main">
      <section v-if="section === 'appearance'" class="settings__panel">
        <h2>Appearance</h2>
        <p class="settings__lead">Tema del panel. Se guarda en este navegador.</p>
        <fieldset class="settings__fieldset">
          <legend>Tema</legend>
          <label class="settings__radio">
            <input
              type="radio"
              name="theme"
              value="light"
              :checked="theme === 'light'"
              @change="onThemeChange('light')"
            />
            Light
          </label>
          <label class="settings__radio">
            <input
              type="radio"
              name="theme"
              value="dark"
              :checked="theme === 'dark'"
              @change="onThemeChange('dark')"
            />
            Dark
          </label>
          <label class="settings__radio">
            <input
              type="radio"
              name="theme"
              value="system"
              :checked="theme === 'system'"
              @change="onThemeChange('system')"
            />
            System
          </label>
        </fieldset>
      </section>

      <section v-else class="settings__panel">
        <h2>Analytics</h2>
        <p class="settings__lead">
          Espacio preparado para métricas. Todavía no hay dashboard; los datos
          viven en conversaciones y mensajes existentes.
        </p>
        <ul class="settings__future">
          <li>Conversaciones recibidas / resueltas</li>
          <li>Volumen por canal y período</li>
          <li>Tiempos de respuesta</li>
          <li>Takeovers por operador (auditoría en mensajes system)</li>
          <li>Uso del agente interno</li>
        </ul>
        <p class="settings__note">
          Fuente prevista: Conversation, Message, tags
          <code>bot-apagado</code> / <code>bot-activo</code>,
          <code>handling_mode</code>.
        </p>
      </section>
    </main>
  </div>
</template>
