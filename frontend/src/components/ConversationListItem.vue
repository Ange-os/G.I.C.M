<script setup lang="ts">
import {
  type Conversation,
  STATUS_LABELS,
  displayContact,
  formatDateTime,
} from "../api/client";

defineProps<{
  conversation: Conversation;
  selected?: boolean;
}>();
</script>

<template>
  <article class="conversation-item" :class="{ selected }">
    <div class="conversation-item__top">
      <strong>{{ displayContact(conversation) }}</strong>
      <time>{{ formatDateTime(conversation.updated_at) }}</time>
    </div>
    <div class="conversation-item__meta">
      <span class="badge" :class="`badge--${conversation.status}`">
        {{ STATUS_LABELS[conversation.status] }}
      </span>
      <span class="channel">{{ conversation.channel }}</span>
      <span
        v-if="conversation.channel === 'whatsapp' && conversation.whatsapp_provider"
        class="tag"
      >
        {{ conversation.whatsapp_provider }}
      </span>
      <span v-else-if="conversation.channel === 'instagram'" class="tag">meta</span>
    </div>
    <div v-if="conversation.tags.length" class="conversation-item__tags">
      <span v-for="tag in conversation.tags" :key="tag.id" class="tag">{{ tag.name }}</span>
    </div>
  </article>
</template>
