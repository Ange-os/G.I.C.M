# Setup local + n8n producción (xia.ar)

Configuración actual para tu entorno:

| Componente | URL / ubicación |
|------------|-----------------|
| Backend API | `http://127.0.0.1:8000` (local) |
| Backend público (localtunnel) | `https://ninety-colts-accept.loca.lt` |
| n8n webhook | `https://n8n.xia.ar/webhook/conversa-events` |
| Frontend | `http://localhost:5173` (local) |
| PostgreSQL + Redis | Docker en tu PC |

## Flujo de datos

```
Postman / YCloud
    → https://ninety-colts-accept.loca.lt/webhooks/ycloud/inbound
    → Backend local guarda mensaje
    → POST https://n8n.xia.ar/webhook/conversa-events
    → n8n (Cohere)
    → POST https://ninety-colts-accept.loca.lt/webhooks/n8n/inbound
    → Backend guarda respuesta + YCloud (si configurado)
```

## 1. Servicios en tu PC

```powershell
cd D:\Proyecode\conversa-platform
docker compose up postgres redis -d
```

```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm run dev
```

## 2. Localtunnel (terminal aparte)

```powershell
npx localtunnel --port 8000
```

URL actual: **https://ninety-colts-accept.loca.lt**

> Si reiniciás localtunnel y cambia la URL, actualizá:
> - `backend/.env` → `PUBLIC_API_URL`
> - Nodos HTTP en n8n → URL `/webhooks/n8n/inbound`
> - Panel YCloud → URL `/webhooks/ycloud/inbound`

Primera vez: abrí `https://ninety-colts-accept.loca.lt/health` en el navegador (localtunnel puede pedir confirmación).

## 2b. Backend `.env` (ya configurado)

```env
N8N_WEBHOOK_URL=https://n8n.xia.ar/webhook/conversa-events
N8N_API_KEY=conversa-n8n-local-2026
PUBLIC_API_URL=https://ninety-colts-accept.loca.lt
```

Completá `YCLOUD_API_KEY` si querés enviar WhatsApp real.

**Reiniciá uvicorn** después de editar `.env`.

## 3. n8n (https://n8n.xia.ar)

### Workflow activo

1. Workflow **Conversa Platform - WhatsApp Bot** → **Activado**
2. Nodos HTTP deben apuntar a:
   ```
   https://ninety-colts-accept.loca.lt/webhooks/n8n/inbound
   ```
3. Header obligatorio:
   ```
   X-N8N-API-Key: conversa-n8n-local-2026
   Bypass-Tunnel-Reminder: true
   ```
4. Credencial **cohere key** asignada al nodo Cohere

Podés reimportar `docs/n8n-conversa-platform.json` o editar los 2 nodos HTTP a mano.

## 4. Prueba rápida

### A) Health por tunnel

```
GET https://ninety-colts-accept.loca.lt/health
```

### B) Simular mensaje cliente

```
POST https://ninety-colts-accept.loca.lt/webhooks/ycloud/inbound
Content-Type: application/json

{
  "whatsappInboundMessage": {
    "type": "text",
    "from": "5491112345678",
    "text": { "body": "Hola, quiero una camiseta" }
  }
}
```

### C) Verificar

- n8n → **Executions** → debe aparecer una ejecución nueva
- http://localhost:5173/inbox → mensaje cliente + respuesta bot
- Si falla el último nodo HTTP en n8n → revisar URL tunnel y header `Bypass-Tunnel-Reminder`

## 5. YCloud (WhatsApp real)

En panel YCloud, webhook entrante:

```
https://ninety-colts-accept.loca.lt/webhooks/ycloud/inbound
```

## URLs de referencia

| Uso | URL |
|-----|-----|
| Health | `https://ninety-colts-accept.loca.lt/health` |
| Webhook YCloud | `https://ninety-colts-accept.loca.lt/webhooks/ycloud/inbound` |
| n8n → Conversa | `https://ninety-colts-accept.loca.lt/webhooks/n8n/inbound` |
| Conversa → n8n | `https://n8n.xia.ar/webhook/conversa-events` |
| Inbox UI | `http://localhost:5173/inbox` |
| API docs local | `http://127.0.0.1:8000/docs` |
