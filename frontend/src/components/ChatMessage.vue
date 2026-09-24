<script setup lang="ts">
import { type Message, SENDER_LABELS, formatDateTime } from "../api/client";

defineProps<{
  message: Message;
}>();
</script>

<template>
  <div
    class="chat-message"
    :class="{
      inbound: message.direction === 'inbound',
      outbound: message.direction === 'outbound',
    }"
  >
    <div class="chat-message__bubble">
      <div class="chat-message__meta">
        <span class="chat-message__sender">{{ SENDER_LABELS[message.sender_type] }}</span>
        <time>{{ formatDateTime(message.created_at) }}</time>
      </div>
      <p v-if="message.content" class="chat-message__text">{{ message.content }}</p>
      <p v-else-if="message.media_url" class="chat-message__text muted">
        <a :href="message.media_url" target="_blank" rel="noopener">Ver adjunto</a>
      </p>
      <p v-else class="chat-message__text muted">Sin contenido</p>
    </div>
  </div>
</template>
