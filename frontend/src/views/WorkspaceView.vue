<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import ActionsCatalogView from "./ActionsCatalogView.vue";
import AssistantView from "./AssistantView.vue";
import InboxView from "./InboxView.vue";
import type { CatalogAction } from "../api/client";

const STORAGE_KEY = "conversa.inboxWidth";
const INBOX_MIN = 480;
const SIDE_MIN = 340;
const DEFAULT_RATIO = 0.56;

const workspaceRef = ref<HTMLElement | null>(null);
const assistantRef = ref<InstanceType<typeof AssistantView> | null>(null);
const inboxWidth = ref(720);
const resizing = ref(false);
const agentBusy = ref(false);
const activeActionId = ref<string | null>(null);

const inboxStyle = computed(() => ({
  width: `${inboxWidth.value}px`,
}));

function clampInboxWidth(width: number, total: number) {
  const max = Math.max(INBOX_MIN, total - SIDE_MIN);
  return Math.min(Math.max(width, INBOX_MIN), max);
}

function readStoredWidth(total: number) {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    const parsed = Number(raw);
    if (Number.isFinite(parsed)) return clampInboxWidth(parsed, total);
  }
  return clampInboxWidth(Math.round(total * DEFAULT_RATIO), total);
}

function syncFromLayout() {
  const total = workspaceRef.value?.clientWidth ?? 0;
  if (total <= 0) return;
  inboxWidth.value = readStoredWidth(total);
}

function onPointerMove(event: PointerEvent) {
  if (!resizing.value || !workspaceRef.value) return;
  const left = workspaceRef.value.getBoundingClientRect().left;
  const total = workspaceRef.value.clientWidth;
  inboxWidth.value = clampInboxWidth(event.clientX - left, total);
}

function stopResize() {
  if (!resizing.value) return;
  resizing.value = false;
  localStorage.setItem(STORAGE_KEY, String(inboxWidth.value));
  document.body.classList.remove("is-resizing-workspace");
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerup", stopResize);
}

function startResize(event: PointerEvent) {
  if (window.matchMedia("(max-width: 1100px)").matches) return;
  event.preventDefault();
  resizing.value = true;
  document.body.classList.add("is-resizing-workspace");
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", stopResize);
  onPointerMove(event);
}

function onWindowResize() {
  if (!workspaceRef.value) return;
  inboxWidth.value = clampInboxWidth(inboxWidth.value, workspaceRef.value.clientWidth);
}

async function onSelectAction(action: CatalogAction) {
  await assistantRef.value?.startAction(action.starter_message, action.id);
}

onMounted(() => {
  syncFromLayout();
  window.addEventListener("resize", onWindowResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", onWindowResize);
  stopResize();
});
</script>

<template>
  <div ref="workspaceRef" class="workspace" :class="{ 'workspace--resizing': resizing }">
    <div class="workspace__inbox" :style="inboxStyle">
      <InboxView />
      <div
        class="workspace__resizer"
        role="separator"
        aria-orientation="vertical"
        aria-label="Ajustar ancho del inbox"
        :aria-valuemin="INBOX_MIN"
        :aria-valuenow="inboxWidth"
        tabindex="0"
        @pointerdown="startResize"
      />
    </div>
    <div class="workspace__side">
      <div class="workspace__tools">
        <ActionsCatalogView
          :busy="agentBusy"
          :active-action-id="activeActionId"
          @select="onSelectAction"
        />
      </div>
      <div class="workspace__agent">
        <AssistantView
          ref="assistantRef"
          @busy-change="agentBusy = $event"
          @action-change="activeActionId = $event"
        />
      </div>
    </div>
  </div>
</template>
