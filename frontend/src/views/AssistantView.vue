<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import {
  type AssistantMessage,
  type AssistantStatus,
  type AssistantThread,
  createAssistantThread,
  fetchAssistantMessages,
  fetchAssistantStatus,
  fetchAssistantThreads,
  sendAssistantMessage,
} from "../api/client";

const status = ref<AssistantStatus | null>(null);
const threads = ref<AssistantThread[]>([]);
const messages = ref<AssistantMessage[]>([]);
const activeId = ref<string | null>(null);
const draft = ref("");
const loading = ref(true);
const sending = ref(false);
const error = ref<string | null>(null);
const threadRef = ref<HTMLElement | null>(null);

async function scrollToBottom() {
  await nextTick();
  if (threadRef.value) {
    threadRef.value.scrollTop = threadRef.value.scrollHeight;
  }
}

async function openThread(threadId: string) {
  activeId.value = threadId;
  error.value = null;
  try {
    messages.value = await fetchAssistantMessages(threadId);
    await scrollToBottom();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo abrir la conversación";
  }
}

function startNew() {
  activeId.value = null;
  messages.value = [];
  error.value = null;
  draft.value = "";
}

async function submit() {
  const content = draft.value.trim();
  if (!content || sending.value) return;
  sending.value = true;
  error.value = null;
  try {
    let threadId = activeId.value;
    if (!threadId) {
      const thread = await createAssistantThread();
      threads.value = [thread, ...threads.value];
      threadId = thread.id;
      activeId.value = threadId;
    }
    const result = await sendAssistantMessage(threadId, content);
    draft.value = "";
    messages.value = result.messages;
    threads.value = threads.value.map((thread) =>
      thread.id === result.thread.id ? result.thread : thread,
    );
    await scrollToBottom();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo consultar al asistente";
  } finally {
    sending.value = false;
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

function onSelectThread(event: Event) {
  const value = (event.target as HTMLSelectElement).value;
  if (!value) {
    startNew();
    return;
  }
  openThread(value);
}

onMounted(async () => {
  try {
    const [assistantStatus, assistantThreads] = await Promise.all([
      fetchAssistantStatus(),
      fetchAssistantThreads(),
    ]);
    status.value = assistantStatus;
    threads.value = assistantThreads;
    if (assistantThreads[0]) {
      await openThread(assistantThreads[0].id);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo cargar el asistente";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="assistant-dock">
    <header class="panel-head">
      <div>
        <h2>Agente</h2>
        <p>{{ status?.model || "DeepSeek" }}</p>
      </div>
      <div class="panel-head__actions">
        <select
          class="panel-select"
          :value="activeId || ''"
          :disabled="loading"
          @change="onSelectThread"
        >
          <option value="">Nueva conversación</option>
          <option v-for="thread in threads" :key="thread.id" :value="thread.id">
            {{ thread.title }}
          </option>
        </select>
        <button class="btn-ghost" type="button" @click="startNew">Nueva</button>
      </div>
    </header>

    <p v-if="status && !status.configured" class="error assistant-dock__notice">
      Falta DEEPSEEK_API_KEY en el backend. Pegala en el .env y reiniciá la API.
    </p>

    <section ref="threadRef" class="assistant-dock__messages">
      <div v-if="loading" class="inbox__empty">Cargando...</div>
      <div v-else-if="!messages.length" class="assistant-dock__empty">
        <p>Preguntá sobre el inbox. Lee contactos y mensajes recientes. No envía WhatsApp.</p>
      </div>
      <article
        v-for="message in messages"
        :key="message.id"
        class="assistant-bubble"
        :class="`assistant-bubble--${message.role}`"
      >
        <p>{{ message.content }}</p>
      </article>
      <p v-if="sending" class="assistant-app__pending">Consultando el inbox…</p>
    </section>

    <footer class="agent-reply">
      <p v-if="error" class="error">{{ error }}</p>
      <div class="agent-reply__row">
        <textarea
          v-model="draft"
          class="agent-reply__input"
          rows="2"
          placeholder="Ejemplo: ¿quién escribió hoy y qué pidió?"
          :disabled="sending"
          @keydown="onKeydown"
        />
        <button class="btn-primary" type="button" :disabled="sending || !draft.trim()" @click="submit">
          {{ sending ? "..." : "Enviar" }}
        </button>
      </div>
    </footer>
  </div>
</template>
