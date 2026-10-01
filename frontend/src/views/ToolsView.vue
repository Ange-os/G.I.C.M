<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { convertPdfToText, fetchToolsStatus, sendToolEmail, type PdfTextResult } from "../api/client";
import { getSessionUser } from "../api/session";

type ToolAction = "pdf" | "mail";

const isAdmin = computed(() => getSessionUser()?.role === "admin");
const mailConfigured = ref(true);

const pdfFile = ref<File | null>(null);
const pdfResult = ref<PdfTextResult | null>(null);
const pdfLoading = ref(false);
const pdfError = ref<string | null>(null);
const copied = ref(false);

const mailTo = ref("");
const mailSubject = ref("");
const mailBody = ref("");
const mailLoading = ref(false);
const mailError = ref<string | null>(null);
const mailSent = ref(false);

const open = ref(false);
const activeAction = ref<ToolAction | null>(null);
const panelRef = ref<HTMLElement | null>(null);
const statusNote = ref("");

function collapse() {
  open.value = false;
  activeAction.value = null;
}

function toggle() {
  if (open.value) {
    collapse();
    return;
  }
  open.value = true;
  activeAction.value = null;
  statusNote.value = "";
}

function selectAction(action: ToolAction) {
  activeAction.value = action;
  statusNote.value = "";
  pdfError.value = null;
  mailError.value = null;
  mailSent.value = false;
}

function finishAction(note: string) {
  statusNote.value = note;
  collapse();
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
  finishAction("Texto del PDF copiado");
}

async function sendMail() {
  if (!isAdmin.value || mailLoading.value) return;
  mailLoading.value = true;
  mailError.value = null;
  mailSent.value = false;
  try {
    await sendToolEmail(mailTo.value.trim(), mailSubject.value.trim(), mailBody.value.trim());
    mailSent.value = true;
    mailTo.value = "";
    mailSubject.value = "";
    mailBody.value = "";
    finishAction("Mail enviado");
  } catch (e) {
    mailError.value = e instanceof Error ? e.message : "No se pudo enviar el mail";
  } finally {
    mailLoading.value = false;
  }
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
    const status = await fetchToolsStatus();
    mailConfigured.value = status.mail_configured;
  } catch {
    mailConfigured.value = false;
  }
});

onUnmounted(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
  window.removeEventListener("keydown", onKeydown);
});

async function focusPanel() {
  await nextTick();
  panelRef.value?.querySelector<HTMLElement>("button, input, textarea")?.focus();
}

function openAndSelect(action: ToolAction) {
  open.value = true;
  selectAction(action);
  focusPanel();
}
</script>

<template>
  <section ref="panelRef" class="tools-panel" :class="{ 'tools-panel--open': open }">
    <button
      type="button"
      class="tools-panel__toggle"
      :aria-expanded="open"
      aria-controls="tools-panel-body"
      aria-haspopup="menu"
      @click="toggle"
    >
      <span class="tools-panel__toggle-text">
        <strong>Herramientas</strong>
        <span>{{ statusNote || "PDF y mail" }}</span>
      </span>
      <span class="tools-panel__chevron" aria-hidden="true">{{ open ? "▾" : "▸" }}</span>
    </button>

    <div v-show="open" id="tools-panel-body" class="tools-panel__content">
      <div v-if="!activeAction" class="tools-panel__menu" role="menu">
        <button type="button" role="menuitem" class="tools-panel__menu-item" @click="openAndSelect('pdf')">
          <strong>PDF a texto</strong>
          <span>Extraer y copiar el contenido</span>
        </button>
        <button type="button" role="menuitem" class="tools-panel__menu-item" @click="openAndSelect('mail')">
          <strong>Enviar mail</strong>
          <span>Mensaje por SMTP</span>
        </button>
      </div>

      <template v-else>
        <div class="panel-head panel-head--tools">
          <button class="btn-ghost tools-panel__back" type="button" @click="activeAction = null">
            ← Acciones
          </button>
          <div class="panel-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              :aria-selected="activeAction === 'pdf'"
              :class="{ 'panel-tabs__tab--active': activeAction === 'pdf' }"
              @click="selectAction('pdf')"
            >
              PDF
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeAction === 'mail'"
              :class="{ 'panel-tabs__tab--active': activeAction === 'mail' }"
              @click="selectAction('mail')"
            >
              Mail
            </button>
          </div>
        </div>

        <div class="tools-panel__body">
          <div v-if="activeAction === 'pdf'">
            <p class="tools-panel__hint">Subí un PDF con texto. Al copiar, el panel se pliega.</p>
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

          <form v-else class="tools__form" @submit.prevent="sendMail">
            <p v-if="!isAdmin" class="tools-panel__hint">
              Lo envía administración. Con el rol consejo podés ver la herramienta, no usarla.
            </p>
            <p v-else-if="!mailConfigured" class="error">
              Falta SMTP_HOST en el .env del backend. Completalo y reiniciá la API.
            </p>
            <p v-else class="tools-panel__hint">Al enviar, el panel se pliega.</p>
            <label>
              Para
              <input v-model="mailTo" type="email" required :disabled="!isAdmin || mailLoading" />
            </label>
            <label>
              Asunto
              <input
                v-model="mailSubject"
                type="text"
                required
                maxlength="200"
                :disabled="!isAdmin || mailLoading"
              />
            </label>
            <label>
              Mensaje
              <textarea v-model="mailBody" rows="4" required :disabled="!isAdmin || mailLoading" />
            </label>
            <p v-if="mailError" class="error">{{ mailError }}</p>
            <button class="btn-primary" type="submit" :disabled="!isAdmin || mailLoading || !mailConfigured">
              {{ mailLoading ? "Enviando..." : "Enviar" }}
            </button>
          </form>
        </div>
      </template>
    </div>
  </section>
</template>
