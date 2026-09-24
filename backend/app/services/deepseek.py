import httpx

from app.config import settings


class DeepSeekNotConfigured(Exception):
    """Falta la API key de DeepSeek."""


class DeepSeekError(Exception):
    """DeepSeek rechazó o no completó la respuesta."""


async def complete_chat(messages: list[dict[str, str]]) -> str:
    api_key = (settings.deepseek_api_key or "").strip()
    if not api_key:
        raise DeepSeekNotConfigured("Falta DEEPSEEK_API_KEY en el .env del backend")

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.deepseek_model,
                    "messages": messages,
                    "temperature": 0.3,
                    "stream": False,
                },
            )
    except httpx.HTTPError as exc:
        raise DeepSeekError("No se pudo contactar a DeepSeek") from exc

    if response.status_code >= 400:
        detail = _error_detail(response)
        raise DeepSeekError(detail)

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError("DeepSeek respondió sin texto") from exc

    if not content or not str(content).strip():
        raise DeepSeekError("DeepSeek respondió sin texto")
    return str(content).strip()


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        message = body.get("error", {}).get("message")
        if message:
            return str(message)[:400]
    except ValueError:
        pass
    return f"DeepSeek respondió {response.status_code}"
