<script setup lang="ts">
import AssistantView from "./AssistantView.vue";
import InboxView from "./InboxView.vue";
import ToolsView from "./ToolsView.vue";
</script>

<template>
  <div class="workspace">
    <div class="workspace__inbox">
      <InboxView />
    </div>
    <div class="workspace__tools">
      <ToolsView />
    </div>
    <div class="workspace__agent">
      <AssistantView />
    </div>
  </div>
</template>
