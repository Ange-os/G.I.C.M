<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import ActionCard from "../components/ActionCard.vue";
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

const emit = defineEmits<{
  busyChange: [busy: boolean];
  actionChange: [actionId: string | null];
}>();

const status = ref<AssistantStatus | null>(null);
const threads = ref<AssistantThread[]>([]);
const messages = ref<AssistantMessage[]>([]);
const activeId = ref<string | null>(null);
const draft = ref("");
const loading = ref(true);
const sending = ref(false);
const error = ref<string | null>(null);
const threadRef = ref<HTMLElement | null>(null);
const activeActionId = ref<string | null>(null);

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
  activeActionId.value = null;
}

async function sendContent(content: string, options?: { freshThread?: boolean }) {
  const text = content.trim();
  if (!text || sending.value) return;
  sending.value = true;
  error.value = null;
  try {
    let threadId = options?.freshThread ? null : activeId.value;
    if (!threadId) {
      const thread = await createAssistantThread();
      threads.value = [thread, ...threads.value];
      threadId = thread.id;
      activeId.value = threadId;
    }
    const result = await sendAssistantMessage(threadId, text);
    draft.value = "";
    messages.value = result.messages;
    threads.value = threads.value.map((thread) =>
      thread.id === result.thread.id ? result.thread : thread,
    );
    await scrollToBottom();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo consultar al agente";
  } finally {
    sending.value = false;
  }
}

async function submit() {
  await sendContent(draft.value);
}

/** Arranca una acción del catálogo: hilo nuevo + mensaje guía al agente. */
async function startAction(starterMessage: string, actionId?: string) {
  if (sending.value) return;
  startNew();
  activeActionId.value = actionId || null;
  await sendContent(starterMessage, { freshThread: true });
}

async function onActionUpdated(nextMessages: AssistantMessage[]) {
  if (nextMessages.length) {
    messages.value = nextMessages;
    await scrollToBottom();
    return;
  }
  if (activeId.value) {
    await openThread(activeId.value);
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
  activeActionId.value = null;
  openThread(value);
}

watch(sending, (value) => emit("busyChange", value), { immediate: true });
watch(activeActionId, (value) => emit("actionChange", value), { immediate: true });

defineExpose({ startAction });

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
    error.value = e instanceof Error ? e.message : "No se pudo cargar el agente";
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
        <p>{{ status?.model || "DeepSeek" }} · datos {{ status?.domain_data_source || "local" }}</p>
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
        <p>
          Elegí una acción a la izquierda o preguntá directo: convenios, médicos o un mail.
        </p>
      </div>
      <template v-for="message in messages" :key="message.id">
        <article
          class="assistant-bubble"
          :class="`assistant-bubble--${message.role}`"
        >
          <p>{{ message.content }}</p>
        </article>
        <ActionCard
          v-if="message.action"
          :action="message.action"
          @updated="onActionUpdated"
        />
      </template>
      <p v-if="sending" class="assistant-app__pending">Consultando tools…</p>
    </section>

    <footer class="agent-reply">
      <p v-if="error" class="error">{{ error }}</p>
      <div class="agent-reply__row">
        <textarea
          v-model="draft"
          class="agent-reply__input"
          rows="2"
          placeholder="Respondé al agente o escribí una consulta…"
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
