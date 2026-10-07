<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  type Conversation,
  type Message,
  fetchConversation,
  fetchConversations,
  fetchMessages,
  hasTag,
  releaseBot,
  resolveConversation,
  sendAgentMessage,
  takeConversation,
} from "../api/client";
import { CHANNEL_FILTERS, channelLabel, type ChannelId } from "../channels";
import AgentReplyBox from "../components/AgentReplyBox.vue";
import ConversationListItem from "../components/ConversationListItem.vue";
import ChatMessage from "../components/ChatMessage.vue";

const props = defineProps<{
  id?: string;
}>();

const route = useRoute();
const router = useRouter();

const conversations = ref<Conversation[]>([]);
const messages = ref<Message[]>([]);
const selectedConversation = ref<Conversation | null>(null);
const loadingList = ref(true);
const loadingDetail = ref(false);
const actionLoading = ref(false);
const sendingMessage = ref(false);
const error = ref<string | null>(null);
const threadRef = ref<HTMLElement | null>(null);
const channelFilter = ref<ChannelId | "all">("all");

const selectedId = computed(() => props.id || (route.params.id as string | undefined));
const isBotOff = computed(() =>
  selectedConversation.value
    ? selectedConversation.value.handling_mode === "human" ||
      hasTag(selectedConversation.value, "bot-apagado")
    : false,
);
const isResolved = computed(() => selectedConversation.value?.status === "resolved");
const canTake = computed(() => selectedConversation.value && !isBotOff.value && !isResolved.value);
const canReleaseBot = computed(() => selectedConversation.value && isBotOff.value && !isResolved.value);
const canReply = computed(() => selectedConversation.value && isBotOff.value && !isResolved.value);
const replyDisabledReason = computed(() => {
  if (!selectedConversation.value) return "";
  if (isResolved.value) return "La conversación está resuelta.";
  if (!isBotOff.value) return "Tomá la conversación para responder como agente.";
  return "";
});
const handlingLabel = computed(() =>
  isBotOff.value ? "Atención humana" : "Atención automática",
);

const filteredConversations = computed(() => {
  if (channelFilter.value === "all") return conversations.value;
  return conversations.value.filter((c) => c.channel === channelFilter.value);
});

let pollTimer: ReturnType<typeof setInterval> | null = null;
let refreshInFlight = false;

async function scrollToBottom() {
  await nextTick();
  if (threadRef.value) {
    threadRef.value.scrollTop = threadRef.value.scrollHeight;
  }
}

async function loadConversations() {
  try {
    conversations.value = await fetchConversations();
    error.value = null;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Error al cargar conversaciones";
  } finally {
    loadingList.value = false;
  }
}

async function loadConversationDetail(conversationId: string) {
  loadingDetail.value = true;
  try {
    const [conversation, conversationMessages] = await Promise.all([
      fetchConversation(conversationId),
      fetchMessages(conversationId),
    ]);
    selectedConversation.value = conversation;
    messages.value = conversationMessages;
    error.value = null;
    await scrollToBottom();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Error al cargar la conversación";
    selectedConversation.value = null;
    messages.value = [];
  } finally {
    loadingDetail.value = false;
  }
}

function openConversation(conversationId: string) {
  router.push({ name: "inbox", params: { id: conversationId } });
}

async function refreshAll() {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    await loadConversations();
    if (selectedId.value) {
      await loadConversationDetail(selectedId.value);
    }
  } finally {
    refreshInFlight = false;
  }
}

async function handleTake() {
  if (!selectedId.value) return;
  actionLoading.value = true;
  try {
    const result = await takeConversation(selectedId.value);
    selectedConversation.value = result.conversation;
    if (result.message) messages.value = [...messages.value, result.message];
    await loadConversations();
    error.value = null;
    await scrollToBottom();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo tomar la conversación";
  } finally {
    actionLoading.value = false;
  }
}

async function handleReleaseBot() {
  if (!selectedId.value) return;
  actionLoading.value = true;
  try {
    const result = await releaseBot(selectedId.value);
    selectedConversation.value = result.conversation;
    if (result.message) messages.value = [...messages.value, result.message];
    await loadConversations();
    error.value = null;
    await scrollToBottom();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo liberar la conversación";
  } finally {
    actionLoading.value = false;
  }
}

async function handleResolve() {
  if (!selectedId.value) return;
  actionLoading.value = true;
  try {
    const result = await resolveConversation(selectedId.value);
    selectedConversation.value = result.conversation;
    await loadConversations();
    error.value = null;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo resolver la conversación";
  } finally {
    actionLoading.value = false;
  }
}

async function handleSend(content: string) {
  if (!selectedId.value) return;
  sendingMessage.value = true;
  try {
    const result = await sendAgentMessage(selectedId.value, content, true);
    selectedConversation.value = result.conversation;
    if (result.message) messages.value = [...messages.value, result.message];
    await loadConversations();
    error.value = null;
    await scrollToBottom();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo enviar el mensaje";
  } finally {
    sendingMessage.value = false;
  }
}

watch(
  selectedId,
  async (conversationId) => {
    if (conversationId) {
      await loadConversationDetail(conversationId);
    } else {
      selectedConversation.value = null;
      messages.value = [];
    }
  },
  { immediate: true },
);

onMounted(async () => {
  await refreshAll();
  pollTimer = setInterval(refreshAll, 8000);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
  <div class="inbox">
    <aside class="inbox__sidebar">
      <header class="inbox__sidebar-header">
        <div>
          <h1>Inbox</h1>
          <p>
            {{ filteredConversations.length }}
            <template v-if="channelFilter !== 'all'">
              / {{ conversations.length }}
            </template>
            conversaciones
          </p>
        </div>
        <button class="btn-ghost" type="button" @click="refreshAll">Actualizar</button>
      </header>

      <div class="inbox__channel-filters" role="toolbar" aria-label="Filtrar por canal">
        <button
          v-for="opt in CHANNEL_FILTERS"
          :key="opt.id"
          type="button"
          class="inbox__filter-chip"
          :class="{ active: channelFilter === opt.id }"
          :aria-pressed="channelFilter === opt.id"
          @click="channelFilter = opt.id"
        >
          {{ opt.label }}
        </button>
      </div>

      <p v-if="error" class="error inbox__error">{{ error }}</p>

      <div v-if="loadingList" class="inbox__empty">Cargando...</div>
      <div v-else-if="!filteredConversations.length" class="inbox__empty">
        <template v-if="conversations.length">
          No hay conversaciones en este canal.
        </template>
        <template v-else>
          Sin conversaciones. Enviá un mensaje de prueba al webhook.
        </template>
      </div>
      <ul v-else class="inbox__list">
        <li v-for="conversation in filteredConversations" :key="conversation.id">
          <button
            type="button"
            class="inbox__list-button"
            @click="openConversation(conversation.id)"
          >
            <ConversationListItem
              :conversation="conversation"
              :selected="conversation.id === selectedId"
            />
          </button>
        </li>
      </ul>
    </aside>

    <main class="inbox__main">
      <div v-if="!selectedId" class="inbox__placeholder">
        <h2>Seleccioná una conversación</h2>
        <p>Acá vas a ver el hilo de mensajes del cliente.</p>
      </div>

      <div v-else-if="loadingDetail && !selectedConversation" class="inbox__placeholder">
        Cargando conversación...
      </div>

      <template v-else-if="selectedConversation">
        <header class="inbox__main-header">
          <div>
            <h2>
              {{ selectedConversation.contact?.name || selectedConversation.contact?.phone }}
            </h2>
            <p class="inbox__handling-line">
              <span class="channel">{{ channelLabel(selectedConversation.channel) }}</span>
              ·
              <span
                class="handling"
                :class="isBotOff ? 'handling--human' : 'handling--auto'"
              >
                {{ handlingLabel }}
              </span>
            </p>
          </div>
          <div class="inbox__header-actions">
            <div class="inbox__main-tags">
              <span
                v-for="tag in selectedConversation.tags"
                :key="tag.id"
                class="tag"
                :class="{ 'tag--off': tag.name === 'bot-apagado' }"
              >
                {{ tag.name }}
              </span>
            </div>
            <div class="inbox__buttons">
              <button
                v-if="canTake"
                class="btn-primary"
                type="button"
                :disabled="actionLoading"
                @click="handleTake"
              >
                Tomar conversación
              </button>
              <button
                v-if="canReleaseBot"
                class="btn-ghost"
                type="button"
                :disabled="actionLoading"
                @click="handleReleaseBot"
              >
                Liberar conversación
              </button>
              <button
                v-if="!isResolved"
                class="btn-ghost"
                type="button"
                :disabled="actionLoading"
                @click="handleResolve"
              >
                Resolver
              </button>
            </div>
          </div>
        </header>

        <section ref="threadRef" class="inbox__thread">
          <div v-if="!messages.length" class="inbox__empty-thread">
            Todavía no hay mensajes en esta conversación.
          </div>
          <ChatMessage v-for="message in messages" :key="message.id" :message="message" />
        </section>

        <AgentReplyBox
          :disabled="!canReply"
          :disabled-reason="replyDisabledReason"
          :sending="sendingMessage"
          @send="handleSend"
        />
      </template>
    </main>
  </div>
</template>
