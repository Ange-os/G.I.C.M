import httpx

from app.config import settings


class YCloudError(Exception):
    pass


async def send_whatsapp_text(*, to: str, text: str, from_number: str | None = None) -> dict:
    """Envía mensaje de texto por YCloud API v2."""
    api_key = settings.ycloud_api_key
    sender = from_number or settings.ycloud_from_number

    if not api_key:
        raise YCloudError("YCLOUD_API_KEY no configurada")
    if not sender:
        raise YCloudError("YCLOUD_FROM_NUMBER no configurada")

    payload = {
        "from": sender,
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.ycloud.com/v2/whatsapp/messages",
            headers={
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        raise YCloudError(f"YCloud error {response.status_code}: {response.text}")

    return response.json()
