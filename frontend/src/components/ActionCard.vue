<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  type ActionProposal,
  cancelAssistantAction,
  confirmAssistantAction,
} from "../api/client";

const props = defineProps<{
  action: ActionProposal;
}>();

const emit = defineEmits<{
  updated: [messages: import("../api/client").AssistantMessage[]];
}>();

const busy = ref(false);
const error = ref<string | null>(null);
const editing = ref(false);

const draft = reactive({
  to: "",
  subject: "",
  body: "",
});

watch(
  () => props.action,
  (action) => {
    draft.to = String(action.payload.to || "");
    draft.subject = String(action.payload.subject || "");
    draft.body = String(action.payload.body || "");
    editing.value = false;
    error.value = null;
  },
  { immediate: true },
);

const pending = computed(() => props.action.status === "awaiting_confirmation");
const isEmail = computed(() => props.action.action === "send_email");
const isAgreement = computed(
  () =>
    props.action.action === "suspend_agreement" ||
    props.action.action === "activate_agreement",
);

const statusLabel = computed(() => {
  switch (props.action.status) {
    case "awaiting_confirmation":
      return "Pendiente de confirmación";
    case "completed":
      return "Completada";
    case "failed":
      return "Falló";
    case "cancelled":
      return "Cancelada";
    default:
      return props.action.status;
  }
});

async function onConfirm() {
  if (!pending.value || busy.value) return;
  busy.value = true;
  error.value = null;
  try {
    const body = isEmail.value
      ? { to: draft.to, subject: draft.subject, body: draft.body }
      : undefined;
    const result = await confirmAssistantAction(props.action.id, body);
    emit("updated", result.messages);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo confirmar la acción";
  } finally {
    busy.value = false;
  }
}

async function onCancel() {
  if (!pending.value || busy.value) return;
  busy.value = true;
  error.value = null;
  try {
    await cancelAssistantAction(props.action.id);
    emit("updated", []);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo cancelar";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div
    class="action-card"
    :class="{
      'action-card--pending': pending,
      'action-card--done': action.status === 'completed',
      'action-card--failed': action.status === 'failed',
      'action-card--cancelled': action.status === 'cancelled',
    }"
  >
    <header class="action-card__head">
      <div>
        <h3>{{ action.title }}</h3>
        <p>{{ action.summary }}</p>
      </div>
      <span class="action-card__status">{{ statusLabel }}</span>
    </header>

    <div v-if="isEmail" class="action-card__body">
      <template v-if="editing && pending">
        <label>
          Para
          <input v-model="draft.to" type="email" />
        </label>
        <label>
          Asunto
          <input v-model="draft.subject" type="text" />
        </label>
        <label>
          Mensaje
          <textarea v-model="draft.body" rows="6" />
        </label>
      </template>
      <template v-else>
        <p><strong>Para:</strong> {{ draft.to || action.payload.to }}</p>
        <p><strong>Asunto:</strong> {{ draft.subject || action.payload.subject }}</p>
        <pre class="action-card__preview">{{ draft.body || action.payload.body }}</pre>
      </template>
    </div>

    <div v-else-if="isAgreement" class="action-card__body">
      <p><strong>Obra social:</strong> {{ action.payload.organization_name }}</p>
      <p><strong>Especialidad:</strong> {{ action.payload.specialty }}</p>
      <p><strong>Estado actual:</strong> {{ action.payload.current_status_label }}</p>
      <p><strong>Nuevo estado:</strong> {{ action.payload.new_status_label }}</p>
      <p><strong>Médicos afectados:</strong> {{ action.payload.doctor_count }}</p>
    </div>

    <div v-else class="action-card__body">
      <pre class="action-card__preview">{{ JSON.stringify(action.payload, null, 2) }}</pre>
    </div>

    <p v-if="action.error_message" class="error">{{ action.error_message }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <footer v-if="pending" class="action-card__actions">
      <button
        v-if="isEmail"
        class="btn-ghost"
        type="button"
        :disabled="busy"
        @click="editing = !editing"
      >
        {{ editing ? "Vista previa" : "Editar" }}
      </button>
      <button class="btn-ghost" type="button" :disabled="busy" @click="onCancel">
        Cancelar
      </button>
      <button class="btn-primary" type="button" :disabled="busy" @click="onConfirm">
        {{ busy ? "..." : isEmail ? "Enviar mail" : "Confirmar acción" }}
      </button>
    </footer>
  </div>
</template>
