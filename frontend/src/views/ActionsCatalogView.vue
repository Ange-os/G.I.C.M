<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import {
  convertPdfToText,
  fetchActionsCatalog,
  type CatalogAction,
  type PdfTextResult,
} from "../api/client";

const props = defineProps<{
  busy?: boolean;
  activeActionId?: string | null;
}>();

const emit = defineEmits<{
  select: [action: CatalogAction];
}>();

const actions = ref<CatalogAction[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const open = ref(false);
const panelRef = ref<HTMLElement | null>(null);
const statusNote = ref("");
const showPdf = ref(false);

const pdfFile = ref<File | null>(null);
const pdfResult = ref<PdfTextResult | null>(null);
const pdfLoading = ref(false);
const pdfError = ref<string | null>(null);
const copied = ref(false);

const queries = computed(() => actions.value.filter((a) => a.category === "query"));
const mutations = computed(() => actions.value.filter((a) => a.category === "action"));

const triggerLabel = computed(() => {
  if (statusNote.value) return statusNote.value;
  if (props.activeActionId) {
    const current = actions.value.find((a) => a.id === props.activeActionId);
    if (current) return current.title;
  }
  return "Elegí una acción";
});

function collapse() {
  open.value = false;
  showPdf.value = false;
}

function toggle() {
  if (open.value) {
    collapse();
    return;
  }
  open.value = true;
  showPdf.value = false;
  statusNote.value = "";
}

function onSelect(action: CatalogAction) {
  if (props.busy) return;
  emit("select", action);
  statusNote.value = action.title;
  collapse();
}

function openPdf() {
  showPdf.value = true;
  pdfError.value = null;
}

function onFile(event: Event) {
  const input = event.target as HTMLInputElement;
  pdfFile.value = input.files?.[0] ?? null;
  pdfResult.value = null;
  pdfError.value = null;
  copied.value = false;
}

async function convertPdf() {
  if (!pdfFile.value || pdfLoading.value) return;
  pdfLoading.value = true;
  pdfError.value = null;
  copied.value = false;
  try {
    pdfResult.value = await convertPdfToText(pdfFile.value);
  } catch (e) {
    pdfResult.value = null;
    pdfError.value = e instanceof Error ? e.message : "No se pudo leer el PDF";
  } finally {
    pdfLoading.value = false;
  }
}

async function copyText() {
  if (!pdfResult.value?.text) return;
  await navigator.clipboard.writeText(pdfResult.value.text);
  copied.value = true;
  statusNote.value = "Texto del PDF copiado";
  collapse();
}

function onDocumentPointerDown(event: PointerEvent) {
  if (!open.value || !panelRef.value) return;
  const target = event.target as Node | null;
  if (target && !panelRef.value.contains(target)) {
    collapse();
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && open.value) {
    collapse();
  }
}

onMounted(async () => {
  document.addEventListener("pointerdown", onDocumentPointerDown);
  window.addEventListener("keydown", onKeydown);
  try {
    actions.value = await fetchActionsCatalog();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "No se pudo cargar las acciones";
  } finally {
    loading.value = false;
  }
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <div ref="panelRef" class="actions-dropdown" :class="{ 'actions-dropdown--open': open }">
    <button
      type="button"
      class="actions-dropdown__trigger"
      :aria-expanded="open"
      aria-haspopup="menu"
      aria-controls="actions-dropdown-menu"
      @click="toggle"
    >
      <span class="actions-dropdown__trigger-text">
        <strong>Acciones</strong>
        <span>{{ triggerLabel }}</span>
      </span>
      <span class="actions-dropdown__chevron" aria-hidden="true">{{ open ? "▴" : "▾" }}</span>
    </button>

    <div
      v-show="open"
      id="actions-dropdown-menu"
      class="actions-dropdown__menu"
      role="menu"
    >
      <template v-if="!showPdf">
        <p v-if="loading" class="actions-dropdown__hint">Cargando…</p>
        <p v-else-if="error" class="error actions-dropdown__hint">{{ error }}</p>
        <template v-else>
          <div v-if="mutations.length" class="actions-dropdown__group" role="group">
            <p class="actions-dropdown__label">Operaciones</p>
            <button
              v-for="action in mutations"
              :key="action.id"
              type="button"
              role="menuitem"
              class="actions-dropdown__item"
              :class="{ 'actions-dropdown__item--active': activeActionId === action.id }"
              :disabled="busy"
              @click="onSelect(action)"
            >
              <strong>{{ action.title }}</strong>
              <span>{{ action.description }}</span>
            </button>
          </div>

          <div v-if="queries.length" class="actions-dropdown__group" role="group">
            <p class="actions-dropdown__label">Consultas</p>
            <button
              v-for="action in queries"
              :key="action.id"
              type="button"
              role="menuitem"
              class="actions-dropdown__item"
              :class="{ 'actions-dropdown__item--active': activeActionId === action.id }"
              :disabled="busy"
              @click="onSelect(action)"
            >
              <strong>{{ action.title }}</strong>
              <span>{{ action.description }}</span>
            </button>
          </div>

          <p v-if="!actions.length" class="actions-dropdown__hint">
            No hay acciones disponibles para tu rol.
          </p>
        </template>

        <div class="actions-dropdown__divider" />
        <button type="button" role="menuitem" class="actions-dropdown__item" @click="openPdf">
          <strong>PDF a texto</strong>
          <span>Extraer y copiar contenido</span>
        </button>
      </template>

      <div v-else class="actions-dropdown__pdf">
        <button type="button" class="actions-dropdown__back" @click="showPdf = false">
          ← Volver al menú
        </button>
        <p class="actions-dropdown__hint">Subí un PDF con texto. Al copiar, el menú se cierra.</p>
        <label class="tools__file">
          Archivo
          <input type="file" accept="application/pdf,.pdf" @change="onFile" />
        </label>
        <button class="btn-primary" type="button" :disabled="!pdfFile || pdfLoading" @click="convertPdf">
          {{ pdfLoading ? "Leyendo..." : "Extraer texto" }}
        </button>
        <p v-if="pdfError" class="error">{{ pdfError }}</p>
        <div v-if="pdfResult" class="tools__result">
          <div class="tools__result-bar">
            <span>{{ pdfResult.filename }} · {{ pdfResult.pages }} páginas</span>
            <button class="btn-ghost" type="button" @click="copyText">
              {{ copied ? "Copiado" : "Copiar" }}
            </button>
          </div>
          <pre>{{ pdfResult.text }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
