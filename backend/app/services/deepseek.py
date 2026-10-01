from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings


class DeepSeekNotConfigured(Exception):
    """Falta la API key de DeepSeek."""


class DeepSeekError(Exception):
    """DeepSeek rechazó o no completó la respuesta."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class ChatCompletionResult:
    content: str | None
    tool_calls: list[ToolCall]


async def complete_chat(messages: list[dict[str, str]]) -> str:
    result = await complete_chat_with_tools(messages, tools=None)
    if not result.content or not result.content.strip():
        raise DeepSeekError("DeepSeek respondió sin texto")
    return result.content.strip()


async def complete_chat_with_tools(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> ChatCompletionResult:
    api_key = (settings.deepseek_api_key or "").strip()
    if not api_key:
        raise DeepSeekNotConfigured("Falta DEEPSEEK_API_KEY en el .env del backend")

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    payload: dict = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": 0.2,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise DeepSeekError("No se pudo contactar a DeepSeek") from exc

    if response.status_code >= 400:
        raise DeepSeekError(_error_detail(response))

    data = response.json()
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError("DeepSeek respondió sin mensaje") from exc

    raw_calls = message.get("tool_calls") or []
    tool_calls: list[ToolCall] = []
    for item in raw_calls:
        try:
            tool_calls.append(
                ToolCall(
                    id=str(item["id"]),
                    name=str(item["function"]["name"]),
                    arguments=str(item["function"].get("arguments") or "{}"),
                )
            )
        except (KeyError, TypeError):
            continue

    content = message.get("content")
    content_str = str(content).strip() if content else None
    if not tool_calls and not content_str:
        raise DeepSeekError("DeepSeek respondió sin texto")
    return ChatCompletionResult(content=content_str, tool_calls=tool_calls)


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        message = body.get("error", {}).get("message")
        if message:
            return str(message)[:400]
    except ValueError:
        pass
    return f"DeepSeek respondió {response.status_code}"
