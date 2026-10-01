import { clearSession, getToken, saveSession, type SessionUser } from "./session";

const API_BASE = import.meta.env.VITE_API_URL || "/api";
const REQUEST_TIMEOUT_MS = 10000;

function authHeaders(path: string): HeadersInit {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token && path !== "/auth/login") {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function handleUnauthorized(path: string, response: Response) {
  if (response.status === 401 && path !== "/auth/login" && getToken()) {
    clearSession();
  }
}

async function parseError(response: Response) {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join(", ");
    }
  } catch {
    // ignore
  }
  return `API error ${response.status}`;
}

export async function apiGet<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: authHeaders(path),
      signal: controller.signal,
    });
    if (!response.ok) {
      handleUnauthorized(path, response);
      throw new Error(await parseError(response));
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("La API no respondió a tiempo. Verificá que el backend y PostgreSQL estén activos.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function apiPost<T>(path: string, body?: unknown, timeoutMs = REQUEST_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(path) },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) {
      handleUnauthorized(path, response);
      throw new Error(await parseError(response));
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("La API no respondió a tiempo. Verificá que el backend y PostgreSQL estén activos.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export interface Contact {
  id: string;
  phone: string;
  name: string | null;
}

export interface Tag {
  id: string;
  name: string;
  description?: string | null;
}

export interface Conversation {
  id: string;
  contact_id: string;
  status: "open" | "pending_human" | "resolved";
  channel: "whatsapp" | "web";
  created_at: string;
  updated_at: string;
  contact?: Contact | null;
  tags: Tag[];
}

export interface Message {
  id: string;
  conversation_id: string;
  direction: "inbound" | "outbound";
  sender_type: "contact" | "bot" | "agent" | "system";
  content: string | null;
  media_url: string | null;
  created_at: string;
}

export interface ConversationActionResponse {
  conversation: Conversation;
  message: Message | null;
}

export function fetchConversations() {
  return apiGet<Conversation[]>("/conversations");
}

export function fetchConversation(id: string) {
  return apiGet<Conversation>(`/conversations/${id}`);
}

export function fetchMessages(conversationId: string) {
  return apiGet<Message[]>(`/conversations/${conversationId}/messages`);
}

export function takeConversation(conversationId: string) {
  return apiPost<ConversationActionResponse>(`/conversations/${conversationId}/take`);
}

export function releaseBot(conversationId: string) {
  return apiPost<ConversationActionResponse>(`/conversations/${conversationId}/release-bot`);
}

export function resolveConversation(conversationId: string) {
  return apiPost<ConversationActionResponse>(`/conversations/${conversationId}/resolve`);
}

export function sendAgentMessage(
  conversationId: string,
  content: string,
  sendWhatsapp = true,
) {
  return apiPost<ConversationActionResponse>(`/conversations/${conversationId}/messages`, {
    content,
    send_whatsapp: sendWhatsapp,
  });
}

export function checkHealth() {
  return apiGet<{ status: string }>("/health");
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: SessionUser;
}

export async function login(email: string, password: string) {
  const result = await apiPost<LoginResponse>("/auth/login", { email, password });
  saveSession(result.access_token, result.user);
  return result.user;
}

export function fetchMe() {
  return apiGet<SessionUser>("/auth/me");
}

export interface AssistantThread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ActionProposal {
  id: string;
  thread_id: string;
  message_id: string | null;
  action: string;
  title: string;
  summary: string;
  status:
    | "awaiting_confirmation"
    | "confirmed"
    | "executing"
    | "completed"
    | "failed"
    | "cancelled"
    | "expired";
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error_message: string | null;
  requires_confirmation: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssistantMessage {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  action?: ActionProposal | null;
}

export interface AssistantStatus {
  configured: boolean;
  model: string;
  domain_data_source?: string;
  agent_enabled?: boolean;
}

export interface AssistantSendResponse {
  thread: AssistantThread;
  messages: AssistantMessage[];
}

export interface ActionConfirmResponse {
  proposal: ActionProposal;
  message: AssistantMessage;
  messages: AssistantMessage[];
}

const ASSISTANT_TIMEOUT_MS = 120000;

export interface CatalogAction {
  id: string;
  title: string;
  description: string;
  starter_message: string;
  category: "action" | "query" | string;
}

export function fetchAssistantStatus() {
  return apiGet<AssistantStatus>("/assistant/status");
}

export function fetchActionsCatalog() {
  return apiGet<CatalogAction[]>("/assistant/actions-catalog");
}

export function fetchAssistantThreads() {
  return apiGet<AssistantThread[]>("/assistant/threads");
}

export function createAssistantThread() {
  return apiPost<AssistantThread>("/assistant/threads");
}

export function fetchAssistantMessages(threadId: string) {
  return apiGet<AssistantMessage[]>(`/assistant/threads/${threadId}/messages`);
}

export function sendAssistantMessage(threadId: string, content: string) {
  return apiPost<AssistantSendResponse>(
    `/assistant/threads/${threadId}/messages`,
    { content },
    ASSISTANT_TIMEOUT_MS,
  );
}

export function confirmAssistantAction(
  proposalId: string,
  body?: { to?: string; subject?: string; body?: string },
) {
  return apiPost<ActionConfirmResponse>(
    `/assistant/actions/${proposalId}/confirm`,
    body || {},
    60000,
  );
}

export function cancelAssistantAction(proposalId: string) {
  return apiPost<{ proposal: ActionProposal }>(`/assistant/actions/${proposalId}/cancel`);
}

export interface PdfTextResult {
  filename: string;
  pages: number;
  text: string;
}

export interface ToolsStatus {
  mail_configured: boolean;
}

export function fetchToolsStatus() {
  return apiGet<ToolsStatus>("/tools/status");
}

export async function convertPdfToText(file: File): Promise<PdfTextResult> {
  const form = new FormData();
  form.append("file", file);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(`${API_BASE}/tools/pdf-to-text`, {
      method: "POST",
      headers: authHeaders("/tools/pdf-to-text"),
      body: form,
      signal: controller.signal,
    });
    if (!response.ok) {
      handleUnauthorized("/tools/pdf-to-text", response);
      throw new Error(await parseError(response));
    }
    return response.json() as Promise<PdfTextResult>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("La API no respondió a tiempo. Verificá que el backend esté activo.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export function sendToolEmail(to: string, subject: string, body: string) {
  return apiPost<{ sent: boolean }>("/tools/email", { to, subject, body }, 30000);
}

export const STATUS_LABELS: Record<Conversation["status"], string> = {
  open: "Abierta",
  pending_human: "Esperando humano",
  resolved: "Resuelta",
};

export const SENDER_LABELS: Record<Message["sender_type"], string> = {
  contact: "Cliente",
  bot: "Bot",
  agent: "Agente",
  system: "Sistema",
};

export function formatDateTime(value: string) {
  return new Date(value).toLocaleString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function displayContact(conversation: Conversation) {
  return conversation.contact?.name || conversation.contact?.phone || "Sin contacto";
}

export function hasTag(conversation: Conversation, tagName: string) {
  return conversation.tags.some((tag) => tag.name === tagName);
}
