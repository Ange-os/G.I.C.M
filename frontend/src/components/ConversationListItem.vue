<script setup lang="ts">
import { computed } from "vue";
import {
  type Conversation,
  STATUS_LABELS,
  contactPicture,
  contactUsername,
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

const picture = computed(() => contactPicture(props.conversation));
const username = computed(() => contactUsername(props.conversation));
const initials = computed(() => {
  const label = displayContact(props.conversation).trim();
  const parts = label.replace(/^@/, "").split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
});
</script>

<template>
  <article
    class="conversation-item"
    :class="[channelWashClass(conversation.channel), { selected }]"
  >
    <div class="conversation-item__row">
      <div class="contact-avatar" aria-hidden="true">
        <img v-if="picture" :src="picture" alt="" loading="lazy" referrerpolicy="no-referrer" />
        <span v-else>{{ initials }}</span>
      </div>
      <div class="conversation-item__body">
        <div class="conversation-item__top">
          <strong>{{ displayContact(conversation) }}</strong>
          <time>{{ formatDateTime(conversation.updated_at) }}</time>
        </div>
        <p v-if="username && conversation.contact?.name" class="conversation-item__handle">
          @{{ username }}
        </p>
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
      </div>
    </div>
  </article>
</template>
