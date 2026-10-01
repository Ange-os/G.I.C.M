"""Creación, confirmación y ejecución de ActionProposal."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.permissions import can_execute_action
from app.domain.factory import get_domain_repository
from app.models.domain import ActionProposal, ActionProposalStatus, AgreementStatus
from app.models.entities import AssistantMessage, AssistantRole, User
from app.services.mailer import MailError, MailNotConfigured, send_email


async def get_proposal(
    db: AsyncSession,
    user: User,
    proposal_id: UUID,
) -> ActionProposal | None:
    stmt = select(ActionProposal).where(
        ActionProposal.id == proposal_id,
        ActionProposal.user_id == user.id,
    )
    return await db.scalar(stmt)


async def list_proposals_for_messages(
    db: AsyncSession,
    message_ids: list[UUID],
) -> dict[UUID, ActionProposal]:
    if not message_ids:
        return {}
    stmt = select(ActionProposal).where(ActionProposal.message_id.in_(message_ids))
    rows = list((await db.scalars(stmt)).all())
    return {row.message_id: row for row in rows if row.message_id}


async def confirm_proposal(
    db: AsyncSession,
    user: User,
    proposal_id: UUID,
    *,
    payload_overrides: dict | None = None,
) -> tuple[ActionProposal, AssistantMessage]:
    proposal = await get_proposal(db, user, proposal_id)
    if not proposal:
        raise LookupError("Propuesta no encontrada")
    if proposal.status != ActionProposalStatus.AWAITING_CONFIRMATION:
        raise ValueError(f"La propuesta ya está en estado «{proposal.status.value}»")
    if not can_execute_action(user, proposal.action):
        raise PermissionError("No tenés permiso para ejecutar esta acción")

    if payload_overrides:
        merged = dict(proposal.payload or {})
        for key in ("to", "subject", "body"):
            if key in payload_overrides and payload_overrides[key] is not None:
                merged[key] = str(payload_overrides[key]).strip()
        proposal.payload = merged

    proposal.status = ActionProposalStatus.EXECUTING
    proposal.updated_at = datetime.now(timezone.utc)
    await db.flush()

    try:
        result = await _execute(db, proposal)
    except (MailNotConfigured, MailError, LookupError, ValueError, PermissionError) as exc:
        proposal.status = ActionProposalStatus.FAILED
        proposal.error_message = str(exc)
        proposal.updated_at = datetime.now(timezone.utc)
        message = AssistantMessage(
            thread_id=proposal.thread_id,
            role=AssistantRole.ASSISTANT,
            content=f"No se pudo completar la acción: {exc}",
        )
        db.add(message)
        await db.flush()
        return proposal, message

    proposal.status = ActionProposalStatus.COMPLETED
    proposal.result = result
    proposal.error_message = None
    proposal.updated_at = datetime.now(timezone.utc)

    content = result.get("message") or "Acción completada."
    message = AssistantMessage(
        thread_id=proposal.thread_id,
        role=AssistantRole.ASSISTANT,
        content=content,
    )
    db.add(message)
    await db.flush()
    return proposal, message


async def cancel_proposal(
    db: AsyncSession,
    user: User,
    proposal_id: UUID,
) -> ActionProposal:
    proposal = await get_proposal(db, user, proposal_id)
    if not proposal:
        raise LookupError("Propuesta no encontrada")
    if proposal.status != ActionProposalStatus.AWAITING_CONFIRMATION:
        raise ValueError(f"La propuesta ya está en estado «{proposal.status.value}»")
    proposal.status = ActionProposalStatus.CANCELLED
    proposal.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return proposal


async def _execute(db: AsyncSession, proposal: ActionProposal) -> dict:
    if proposal.action == "send_email":
        payload = proposal.payload or {}
        to = (payload.get("to") or "").strip()
        subject = (payload.get("subject") or "").strip()
        body = (payload.get("body") or "").strip()
        if not to or not subject or not body:
            raise ValueError("Faltan datos del mail (to/subject/body)")
        await send_email(to, subject, body)
        return {
            "ok": True,
            "message": f"Mail enviado a {to}.",
            "to": to,
            "subject": subject,
        }

    if proposal.action in {"suspend_agreement", "activate_agreement"}:
        domain = get_domain_repository(db)
        agreement_id = UUID(str((proposal.payload or {}).get("agreement_id")))
        target = (
            AgreementStatus.SUSPENDED
            if proposal.action == "suspend_agreement"
            else AgreementStatus.ACTIVE
        )
        current = await domain.get_agreement(agreement_id)
        if not current:
            raise LookupError("El convenio ya no existe")
        if current.status == target.value:
            label = "suspendido" if target == AgreementStatus.SUSPENDED else "activo"
            raise ValueError(f"El convenio ya está {label}")
        updated = await domain.set_agreement_status(agreement_id, target)
        verb = "suspendió" if target == AgreementStatus.SUSPENDED else "activó"
        return {
            "ok": True,
            "message": (
                f"Se {verb} el convenio de {updated.organization_name} "
                f"para {updated.specialty} ({updated.doctor_count} médicos)."
            ),
            "agreement": updated.model_dump(mode="json"),
        }

    raise ValueError(f"Acción desconocida: {proposal.action}")
