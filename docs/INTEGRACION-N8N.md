# Integración con n8n (migración desde Chatwoot)

Este documento mapea tu workflow **Bot WhatsApp + Chatwoot** al stack **Conversa Platform**.

## Qué reutilizar del workflow actual

| Componente | En tu workflow | En Conversa Platform |
|------------|----------------|----------------------|
| **YCloud inbound** | Webhook n8n `cmn-whatsapp` | `POST /webhooks/ycloud/inbound` en la API |
| **YCloud outbound** | `POST api.ycloud.com/v2/whatsapp/messages` + credencial **Ycloud key** | Misma credencial vía `YCLOUD_API_KEY` + `YCLOUD_FROM_NUMBER`, o `send_whatsapp: true` en n8n inbound |
| **Cohere IA** | `POST api.cohere.com/v2/chat` + credencial **cohere key** | **Igual** — se queda en n8n |
| **Historial chat** | Static Data de n8n (`history_{phone}`) | Opcional en v1; luego en PostgreSQL vía `/conversations/{id}/messages` |
| **Chatwoot contacto** | `GET/POST .../contacts` | Automático en webhook YCloud |
| **Chatwoot conversación** | `GET/POST .../conversations` | Automático en webhook YCloud |
| **Chatwoot mensajes** | `POST .../messages` incoming/outgoing | `POST /webhooks/n8n/inbound` |
| **Etiquetas (bot-apagado)** | No estaba en el workflow viejo | `tags.add: ["bot-apagado"]` en n8n inbound |

## Qué eliminar del workflow

Todos los nodos HTTP hacia `chat.xia.ar` (Chatwoot):

- Buscar Contacto Chatwoot
- HTTP Request7 (crear contacto)
- Buscar Conversacion Existente
- HTTP Request (crear conversación)
- Resolver Conversacion / If / Set nodes de Chatwoot
- HTTP Request8 / HTTP Request9 (guardar mensajes en Chatwoot)

La API Conversa hace eso al recibir el webhook de YCloud.

## Nuevo flujo

```
Cliente WhatsApp
    → YCloud
    → Conversa API (/webhooks/ycloud/inbound)
        → guarda Contact + Conversation + Message
        → emite evento a n8n (N8N_WEBHOOK_URL)
    → n8n (workflow adaptado)
        → IF tags contiene "bot-apagado" → STOP
        → Cohere genera respuesta
        → POST Conversa API (/webhooks/n8n/inbound) con send_whatsapp: true
    → Conversa API envía por YCloud + guarda mensaje outbound
```

## Configuración paso a paso

### 1. Variables en `.env` de Conversa Platform

```env
N8N_WEBHOOK_URL=https://TU-N8N/webhook/conversa-events
N8N_API_KEY=una-clave-secreta
YCLOUD_API_KEY=tu-misma-api-key-de-ycloud
YCLOUD_FROM_NUMBER=5492664866665
```

Usá la misma API key que tenés en n8n como credencial **Ycloud key** (header `X-API-Key`).

### 2. Cambiar webhook en YCloud

**Antes:** YCloud → n8n (`/webhook/cmn-whatsapp`)

**Ahora:** YCloud → Conversa API

```
https://TU-DOMINIO-O-NGROK/webhooks/ycloud/inbound
```

Para prueba local con ngrok:

```bash
ngrok http 8000
# Usar https://xxxx.ngrok.io/webhooks/ycloud/inbound en YCloud
```

### 3. Importar workflow adaptado en n8n

Archivo: `docs/n8n-conversa-platform.json`

1. Importar en n8n
2. Asignar credenciales **cohere key** (ya la tenés)
3. Configurar variable de entorno en n8n o editar nodos HTTP:
   - `CONVERSA_API_URL` → `http://host.docker.internal:8000` (si n8n en Docker) o tu URL pública
   - `N8N_API_KEY` → misma clave del `.env`
4. Activar workflow
5. Copiar URL del webhook `conversa-events` → pegar en `N8N_WEBHOOK_URL`

### 4. Condicional bot-apagado (para panel humano)

Al inicio del workflow n8n:

```
IF {{ $json.conversation.tags }} contains "bot-apagado"
  → No Operation (fin)
ELSE
  → continuar chatbot
```

Para derivar a humano, otro flujo o el mismo bot puede llamar:

```json
POST /webhooks/n8n/inbound
{
  "conversation_id": "{{ $json.conversation.id }}",
  "tags": { "add": ["bot-apagado"], "remove": ["bot-activo"] },
  "status": "pending_human",
  "message": {
    "sender_type": "bot",
    "content": "Te conecto con un asesor humano."
  },
  "send_whatsapp": true
}
```

## Mapeo de payloads

### Evento que recibe n8n (desde Conversa)

```json
{
  "event": "conversation.message.created",
  "conversation": {
    "id": "uuid",
    "status": "open",
    "channel": "whatsapp",
    "tags": ["bot-activo"]
  },
  "contact": {
    "id": "uuid",
    "phone": "54911...",
    "name": null
  },
  "message": {
    "id": "uuid",
    "content": "Hola, quiero info",
    "direction": "inbound",
    "sender_type": "contact"
  },
  "case": null
}
```

### Respuesta que envía n8n a Conversa

```json
{
  "conversation_id": "uuid-de-conversation",
  "message": {
    "sender_type": "bot",
    "content": "Respuesta del bot..."
  },
  "send_whatsapp": true
}
```

Header: `X-N8N-API-Key: tu-clave`

## Formato YCloud que ya usás

Tu workflow extrae:

```
$json.body.whatsappInboundMessage.text.body   → mensaje
$json.body.whatsappInboundMessage.from        → teléfono
$json.body.whatsappInboundMessage.type        → tipo (text, image, etc.)
```

La API Conversa acepta ese mismo formato (con o sin wrapper `body`).

## Seguridad importante

Tu workflow exportado contiene un **token de Chatwoot en texto plano** (`api_access_token`). Aunque dejes de usar Chatwoot, **rotá ese token** en `chat.xia.ar` por si quedó expuesto.

No subas API keys de YCloud/Cohere al repositorio; usá credenciales de n8n y `.env`.

## Prueba rápida sin YCloud (manual)

```bash
# Simular mensaje entrante
curl -X POST http://localhost:8000/webhooks/ycloud/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "body": {
      "whatsappInboundMessage": {
        "type": "text",
        "from": "5491112345678",
        "text": { "body": "Hola, quiero una camiseta" }
      }
    }
  }'

# Ver conversaciones
curl http://localhost:8000/conversations
```

## Próximo paso (Etapa 3)

- Panel Vue inbox para ver conversaciones y responder como agente humano
- Botón "Tomar conversación" + quitar `bot-apagado` al cerrar
