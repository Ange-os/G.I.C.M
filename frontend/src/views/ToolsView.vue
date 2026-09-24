<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { convertPdfToText, fetchToolsStatus, sendToolEmail, type PdfTextResult } from "../api/client";
import { getSessionUser } from "../api/session";

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
const tab = ref<"pdf" | "mail">("pdf");

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
  } catch (e) {
    mailError.value = e instanceof Error ? e.message : "No se pudo enviar el mail";
  } finally {
    mailLoading.value = false;
  }
}

onMounted(async () => {
  try {
    const status = await fetchToolsStatus();
    mailConfigured.value = status.mail_configured;
  } catch {
    mailConfigured.value = false;
  }
});
</script>

<template>
  <section class="tools-panel">
    <header class="panel-head">
      <div>
        <h2>Herramientas</h2>
        <p>PDF y mail, aparte del inbox</p>
      </div>
      <div class="panel-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'pdf'"
          :class="{ 'panel-tabs__tab--active': tab === 'pdf' }"
          @click="tab = 'pdf'"
        >
          PDF
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="tab === 'mail'"
          :class="{ 'panel-tabs__tab--active': tab === 'mail' }"
          @click="tab = 'mail'"
        >
          Mail
        </button>
      </div>
    </header>

    <div class="tools-panel__body">
      <div v-if="tab === 'pdf'">
        <p class="tools-panel__hint">Subí un PDF con texto. Un escaneo sin texto no se puede leer.</p>
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
        <p v-else class="tools-panel__hint">Completá destinatario, asunto y mensaje.</p>
        <label>
          Para
          <input v-model="mailTo" type="email" required :disabled="!isAdmin || mailLoading" />
        </label>
        <label>
          Asunto
          <input v-model="mailSubject" type="text" required maxlength="200" :disabled="!isAdmin || mailLoading" />
        </label>
        <label>
          Mensaje
          <textarea v-model="mailBody" rows="4" required :disabled="!isAdmin || mailLoading" />
        </label>
        <p v-if="mailError" class="error">{{ mailError }}</p>
        <p v-if="mailSent" class="tools__ok">Mail enviado.</p>
        <button class="btn-primary" type="submit" :disabled="!isAdmin || mailLoading || !mailConfigured">
          {{ mailLoading ? "Enviando..." : "Enviar" }}
        </button>
      </form>
    </div>
  </section>
</template>
