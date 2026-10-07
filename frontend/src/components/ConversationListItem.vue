<script setup lang="ts">
import { computed } from "vue";
import {
  type Conversation,
  STATUS_LABELS,
  displayContact,
  formatDateTime,
  hasTag,
} from "../api/client";
import { channelLabel, channelWashClass } from "../channels";

const props = defineProps<{
  conversation: Conversation;
  selected?: boolean;
}>();

const isHuman = computed(
  () =>
    props.conversation.handling_mode === "human" ||
    hasTag(props.conversation, "bot-apagado"),
);
</script>

<template>
  <article
    class="conversation-item"
    :class="[channelWashClass(conversation.channel), { selected }]"
  >
    <div class="conversation-item__top">
      <strong>{{ displayContact(conversation) }}</strong>
      <time>{{ formatDateTime(conversation.updated_at) }}</time>
    </div>
    <div class="conversation-item__meta">
      <span class="badge" :class="`badge--${conversation.status}`">
        {{ STATUS_LABELS[conversation.status] }}
      </span>
      <span class="channel" :title="channelLabel(conversation.channel)">
        {{ channelLabel(conversation.channel) }}
      </span>
      <span
        class="handling"
        :class="isHuman ? 'handling--human' : 'handling--auto'"
        :title="isHuman ? 'Atención humana' : 'Atención automática'"
      >
        {{ isHuman ? "Humano" : "Auto" }}
      </span>
      <span
        v-if="conversation.channel === 'whatsapp' && conversation.whatsapp_provider"
        class="tag"
      >
        {{ conversation.whatsapp_provider }}
      </span>
      <span v-else-if="conversation.channel === 'instagram'" class="tag">meta</span>
      <span v-else-if="conversation.channel === 'web'" class="tag">xia</span>
    </div>
  </article>
</template>
