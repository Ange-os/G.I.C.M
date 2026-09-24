from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.entities import User
from app.routers.auth import get_current_user
from app.schemas.assistant import (
    AssistantMessageCreate,
    AssistantMessageRead,
    AssistantSendResponse,
    AssistantStatusRead,
    AssistantThreadRead,
)
from app.services.assistant import create_thread, get_thread, list_messages, list_threads, send_message
from app.services.deepseek import DeepSeekError, DeepSeekNotConfigured

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/status", response_model=AssistantStatusRead)
async def assistant_status(_: User = Depends(get_current_user)) -> AssistantStatusRead:
    return AssistantStatusRead(
        configured=bool((settings.deepseek_api_key or "").strip()),
        model=settings.deepseek_model,
    )


@router.get("/threads", response_model=list[AssistantThreadRead])
async def get_threads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AssistantThreadRead]:
    threads = await list_threads(db, current_user)
    return [AssistantThreadRead.model_validate(thread) for thread in threads]


@router.post("/threads", response_model=AssistantThreadRead)
async def post_thread(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantThreadRead:
    thread = await create_thread(db, current_user)
    return AssistantThreadRead.model_validate(thread)


@router.get("/threads/{thread_id}/messages", response_model=list[AssistantMessageRead])
async def get_messages(
    thread_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AssistantMessageRead]:
    thread = await get_thread(db, current_user, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Conversación del asistente no encontrada")
    messages = await list_messages(db, thread.id)
    return [AssistantMessageRead.model_validate(message) for message in messages]


@router.post("/threads/{thread_id}/messages", response_model=AssistantSendResponse)
async def post_message(
    thread_id: UUID,
    body: AssistantMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantSendResponse:
    try:
        thread, messages = await send_message(db, current_user, thread_id, body.content)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DeepSeekNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DeepSeekError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AssistantSendResponse(
        thread=AssistantThreadRead.model_validate(thread),
        messages=[AssistantMessageRead.model_validate(message) for message in messages],
    )
