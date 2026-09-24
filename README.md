# Conversa Platform

Monorepo base para un módulo de conversación embebible (estilo Chatwoot lite) con integración **YCloud** (WhatsApp) y **n8n**.

## Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL + Redis
- **Frontend:** Vue 3 + Vite + Vue Router (panel inbox Etapa 3)
- **Infra:** Docker Compose

## Estructura

```
conversa-platform/
├── backend/          # API FastAPI
├── frontend/         # Vue 3 (panel base)
├── docker-compose.yml
└── .env.example
```

## Arranque rápido con Docker

```bash
cd conversa-platform
cp .env.example .env
docker compose up --build
```

Servicios:

| Servicio   | URL                    |
|-----------|------------------------|
| API       | http://localhost:8000  |
| Docs API  | http://localhost:8000/docs |
| Frontend  | http://localhost:5173  |
| PostgreSQL| localhost:5432         |
| Redis     | localhost:6379         |

## Arranque local (sin Docker para API)

### 1. Infraestructura

```bash
docker compose up postgres redis -d
```

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

## Modelos (Etapa 1)

- `Contact` — cliente identificado por teléfono WhatsApp
- `Conversation` — hilo de chat con canal, estado y tags
- `Message` — mensajes inbound/outbound
- `Tag` — etiquetas (`bot-activo`, `bot-apagado`, etc.)

## Endpoints principales

### Health

```
GET /health
```

### Webhook YCloud (entrante)

```
POST /webhooks/ycloud/inbound
```

Recibe mensajes de WhatsApp vía YCloud, crea contacto/conversación/mensaje y emite evento a Redis + n8n (si `N8N_WEBHOOK_URL` está configurado).

### Webhook n8n (acciones)

```
POST /webhooks/n8n/inbound
```

Ejemplo para apagar el bot y enviar mensaje:

```json
{
  "conversation_id": "uuid-de-la-conversacion",
  "tags": {
    "add": ["bot-apagado"],
    "remove": ["bot-activo"]
  },
  "message": {
    "sender_type": "bot",
    "content": "Te conecto con un asesor humano."
  },
  "status": "pending_human"
}
```

### Conversaciones (lectura básica)

```
GET /conversations
GET /conversations/{id}
GET /conversations/{id}/messages
```

## Eventos hacia n8n

Cuando ocurre un mensaje entrante, la API publica:

```json
{
  "event": "conversation.message.created",
  "conversation": {
    "id": "...",
    "status": "open",
    "channel": "whatsapp",
    "tags": ["bot-activo"]
  },
  "contact": {
    "id": "...",
    "phone": "+54911...",
    "name": "Juan"
  },
  "message": {
    "id": "...",
    "content": "Hola",
    "direction": "inbound",
    "sender_type": "contact"
  },
  "case": null
}
```

Configura en `.env`:

```
N8N_WEBHOOK_URL=https://tu-n8n.com/webhook/conversa-events
```

## Condicional en n8n

```
IF {{ $json.conversation.tags }} contains "bot-apagado"
  → no responder automáticamente
ELSE
  → flujo chatbot + herramientas
```

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | Conexión PostgreSQL async |
| `REDIS_URL` | Redis para pub/sub |
| `N8N_WEBHOOK_URL` | Webhook saliente hacia n8n |
| `N8N_API_KEY` | Protege `POST /webhooks/n8n/inbound` |
| `YCLOUD_API_KEY` | API key YCloud (header X-API-Key) |
| `YCLOUD_FROM_NUMBER` | Número emisor WhatsApp (ej. 5492664866665) |
| `YCLOUD_WEBHOOK_SECRET` | Secreto opcional para validar webhooks YCloud |
| `CORS_ORIGINS` | Orígenes permitidos para el frontend |

## Integración n8n + YCloud (desde workflow Chatwoot)

Ver guía completa: [docs/INTEGRACION-N8N.md](docs/INTEGRACION-N8N.md)

Workflow adaptado listo para importar: [docs/n8n-conversa-platform.json](docs/n8n-conversa-platform.json)

Setup local + n8n producción: [docs/SETUP-LOCAL-N8N.md](docs/SETUP-LOCAL-N8N.md)

## Panel inbox (Etapa 3)

Frontend con vista tipo Chatwoot:

| Ruta | Descripción |
|------|-------------|
| `/inbox` | Lista de conversaciones |
| `/inbox/{id}` | Hilo de mensajes de la conversación |

Características:
- Mensajes inbound (cliente) y outbound (bot/agente/sistema)
- Estado, canal y tags visibles
- Auto-refresh cada 5 segundos
- Botón **Actualizar** manual

Abrir: http://localhost:5173/inbox

## Agente humano (Etapa 4)

Desde el detalle de una conversación:

| Acción | Endpoint | Efecto |
|--------|----------|--------|
| **Tomar conversación** | `POST /conversations/{id}/take` | `bot-apagado`, estado `pending_human` |
| **Enviar mensaje** | `POST /conversations/{id}/messages` | Guarda mensaje agente + envía por YCloud si está configurado |
| **Reactivar bot** | `POST /conversations/{id}/release-bot` | `bot-activo`, estado `open` |
| **Resolver** | `POST /conversations/{id}/resolve` | Cierra la conversación |

Flujo típico:
1. Cliente escribe por WhatsApp o Postman
2. Agente abre `/inbox/{id}`
3. Clic en **Tomar conversación**
4. Escribe y envía respuesta
5. Opcional: **Resolver** o **Reactivar bot**

Para enviar por WhatsApp real configurá en `.env`:
```env
YCLOUD_API_KEY=tu-key
YCLOUD_FROM_NUMBER=
```

Sin YCloud configurado, el mensaje **igual se guarda** en el panel; solo quedará `ycloud_error` en el payload interno.

## Próximas etapas

1. Conectar n8n + Cohere (respuestas automáticas del bot)
2. WhatsApp real vía YCloud (webhook entrante con ngrok)
3. WebSocket/SSE tiempo real
4. Módulo ERP `sales`
