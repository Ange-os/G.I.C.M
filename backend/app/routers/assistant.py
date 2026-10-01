from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.catalog import catalog_for_user
from app.assistant.proposals import cancel_proposal, confirm_proposal
from app.config import settings
from app.database import get_db
from app.models.domain import ActionProposal
from app.models.entities import AssistantMessage, User
from app.routers.auth import get_current_user
from app.schemas.assistant import (
    ActionCancelResponse,
    ActionConfirmBody,
    ActionConfirmResponse,
    ActionProposalRead,
    AssistantMessageCreate,
    AssistantMessageRead,
    AssistantSendResponse,
    AssistantStatusRead,
    AssistantThreadRead,
    CatalogActionRead,
)
from app.services.assistant import (
    create_thread,
    get_thread,
    list_threads,
    messages_with_actions,
    send_message,
)
from app.services.deepseek import DeepSeekError, DeepSeekNotConfigured

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _proposal_read(proposal: ActionProposal) -> ActionProposalRead:
    return ActionProposalRead(
        id=proposal.id,
        thread_id=proposal.thread_id,
        message_id=proposal.message_id,
        action=proposal.action,
        title=proposal.title,
        summary=proposal.summary,
        status=proposal.status.value,
        payload=proposal.payload or {},
        result=proposal.result,
        error_message=proposal.error_message,
        requires_confirmation=proposal.status.value == "awaiting_confirmation",
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


def _message_read(
    message: AssistantMessage,
    proposal: ActionProposal | None = None,
) -> AssistantMessageRead:
    return AssistantMessageRead(
        id=message.id,
        thread_id=message.thread_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        action=_proposal_read(proposal) if proposal else None,
    )


@router.get("/status", response_model=AssistantStatusRead)
async def assistant_status(_: User = Depends(get_current_user)) -> AssistantStatusRead:
    return AssistantStatusRead(
        configured=bool((settings.deepseek_api_key or "").strip()),
        model=settings.deepseek_model,
        domain_data_source=settings.domain_data_source,
        agent_enabled=True,
    )


@router.get("/actions-catalog", response_model=list[CatalogActionRead])
async def get_actions_catalog(
    current_user: User = Depends(get_current_user),
) -> list[CatalogActionRead]:
    return [CatalogActionRead.model_validate(item) for item in catalog_for_user(current_user)]


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
    messages, proposals = await messages_with_actions(db, thread.id)
    return [_message_read(message, proposals.get(message.id)) for message in messages]


@router.post("/threads/{thread_id}/messages", response_model=AssistantSendResponse)
async def post_message(
    thread_id: UUID,
    body: AssistantMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantSendResponse:
    try:
        thread, messages, _proposal = await send_message(
            db, current_user, thread_id, body.content
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DeepSeekNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DeepSeekError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    enriched, proposals = await messages_with_actions(db, thread.id)
    return AssistantSendResponse(
        thread=AssistantThreadRead.model_validate(thread),
        messages=[_message_read(message, proposals.get(message.id)) for message in enriched],
    )


@router.post("/actions/{proposal_id}/confirm", response_model=ActionConfirmResponse)
async def post_confirm_action(
    proposal_id: UUID,
    body: ActionConfirmBody | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActionConfirmResponse:
    overrides = body.model_dump(exclude_none=True) if body else None
    try:
        proposal, message = await confirm_proposal(
            db, current_user, proposal_id, payload_overrides=overrides
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    messages, proposals = await messages_with_actions(db, proposal.thread_id)
    return ActionConfirmResponse(
        proposal=_proposal_read(proposal),
        message=_message_read(message),
        messages=[_message_read(item, proposals.get(item.id)) for item in messages],
    )


@router.post("/actions/{proposal_id}/cancel", response_model=ActionCancelResponse)
async def post_cancel_action(
    proposal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActionCancelResponse:
    try:
        proposal = await cancel_proposal(db, current_user, proposal_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ActionCancelResponse(proposal=_proposal_read(proposal))
