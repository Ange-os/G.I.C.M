<script setup lang="ts">
import { computed, ref } from "vue";

const props = defineProps<{
  disabled?: boolean;
  disabledReason?: string;
  sending?: boolean;
}>();

const emit = defineEmits<{
  send: [content: string];
}>();

const draft = ref("");

const canSend = computed(
  () => !props.disabled && !props.sending && draft.value.trim().length > 0,
);

function submit() {
  const content = draft.value.trim();
  if (!content || !canSend.value) return;
  emit("send", content);
  draft.value = "";
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}
</script>

<template>
  <footer class="agent-reply">
    <p v-if="disabled && disabledReason" class="agent-reply__hint">{{ disabledReason }}</p>
    <div class="agent-reply__row">
      <textarea
        v-model="draft"
        class="agent-reply__input"
        rows="3"
        placeholder="Escribí tu respuesta como agente..."
        :disabled="disabled || sending"
        @keydown="onKeydown"
      />
      <button
        class="btn-primary"
        type="button"
        :disabled="!canSend"
        @click="submit"
      >
        {{ sending ? "Enviando..." : "Enviar" }}
      </button>
    </div>
  </footer>
</template>
