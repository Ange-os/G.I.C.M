"""Tools de acción: preparan propuestas; no ejecutan efectos externos solas."""

from __future__ import annotations

import json
from uuid import UUID

from app.assistant.tools.base import ToolContext, ToolSpec
from app.models.domain import ActionProposal, ActionProposalStatus, AgreementStatus


async def _prepare_email(
    ctx: ToolContext,
    to: str | None = None,
    organization_query: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> str:
    recipient = (to or "").strip()
    org_name = None
    organization_id = None

    if organization_query and organization_query.strip():
        orgs = await ctx.domain.search_organizations(organization_query.strip(), limit=5)
        if not orgs:
            return json.dumps(
                {"error": f"No encontré la obra social «{organization_query}»."},
                ensure_ascii=False,
            )
        if len(orgs) > 1 and not any(
            o.name.lower() == organization_query.strip().lower()
            or (o.short_name or "").lower() == organization_query.strip().lower()
            for o in orgs
        ):
            return json.dumps(
                {
                    "needs_clarification": True,
                    "message": "Hay varias organizaciones. Pedile al usuario que elija una.",
                    "options": [
                        {"id": str(o.id), "name": o.name, "email": o.email} for o in orgs
                    ],
                },
                ensure_ascii=False,
            )
        exact = next(
            (
                o
                for o in orgs
                if o.name.lower() == organization_query.strip().lower()
                or (o.short_name or "").lower() == organization_query.strip().lower()
            ),
            orgs[0],
        )
        org_name = exact.name
        organization_id = str(exact.id)
        if not recipient:
            recipient = (exact.email or "").strip()

    if not recipient:
        return json.dumps(
            {"error": "Falta el destinatario. Buscá la organización o pedí el email."},
            ensure_ascii=False,
        )
    if not subject or not subject.strip():
        subject = f"Consulta desde el círculo médico — {org_name or 'convenios'}"
    if not body or not body.strip():
        body = (
            f"Estimados{(' de ' + org_name) if org_name else ''},\n\n"
            "Nos comunicamos desde el círculo médico para consultar actualizaciones "
            "en convenios de médicos.\n\n"
            "Quedamos a disposición.\n"
            "Saludos cordiales."
        )

    proposal = ActionProposal(
        thread_id=ctx.thread_id,
        user_id=ctx.user.id,
        action="send_email",
        title="Mail preparado",
        summary=f"Enviar mail a {org_name or recipient}",
        status=ActionProposalStatus.AWAITING_CONFIRMATION,
        payload={
            "to": recipient,
            "subject": subject.strip(),
            "body": body.strip(),
            "organization_id": organization_id,
            "organization_name": org_name,
        },
    )
    ctx.db.add(proposal)
    await ctx.db.flush()

    return json.dumps(
        {
            "action_proposal_id": str(proposal.id),
            "action": "send_email",
            "requires_confirmation": True,
            "message": "Propuesta de mail lista. El usuario debe confirmar antes de enviar.",
            "preview": {
                "to": recipient,
                "subject": subject.strip(),
                "organization_name": org_name,
            },
        },
        ensure_ascii=False,
    )


async def _prepare_agreement_status(
    ctx: ToolContext,
    *,
    target_status: AgreementStatus,
    agreement_id: str | None = None,
    organization_query: str | None = None,
    specialty: str | None = None,
) -> str:
    agreement = None
    if agreement_id:
        try:
            agreement = await ctx.domain.get_agreement(UUID(agreement_id))
        except ValueError:
            return json.dumps({"error": "agreement_id inválido"})
    else:
        rows = await ctx.domain.search_agreements(
            organization_query=organization_query,
            specialty=specialty,
            limit=8,
        )
        if not rows:
            return json.dumps(
                {"error": "No encontré un convenio con esos datos."},
                ensure_ascii=False,
            )
        if len(rows) > 1:
            return json.dumps(
                {
                    "needs_clarification": True,
                    "message": "Hay varios convenios. Pedile al usuario que elija uno.",
                    "options": [
                        {
                            "id": str(r.id),
                            "organization": r.organization_name,
                            "specialty": r.specialty,
                            "status": r.status,
                            "doctor_count": r.doctor_count,
                        }
                        for r in rows
                    ],
                },
                ensure_ascii=False,
            )
        agreement = rows[0]

    if not agreement:
        return json.dumps({"error": "Convenio no encontrado"})

    if agreement.status == target_status.value:
        label = "activo" if target_status == AgreementStatus.ACTIVE else "suspendido"
        return json.dumps(
            {
                "error": (
                    f"El convenio de {agreement.organization_name} "
                    f"({agreement.specialty}) ya está {label}."
                )
            },
            ensure_ascii=False,
        )

    action = (
        "activate_agreement"
        if target_status == AgreementStatus.ACTIVE
        else "suspend_agreement"
    )
    title = "Activar convenio" if action == "activate_agreement" else "Suspender convenio"
    new_label = "Activo" if target_status == AgreementStatus.ACTIVE else "Suspendido"
    current_label = "Activo" if agreement.status == "active" else "Suspendido"

    proposal = ActionProposal(
        thread_id=ctx.thread_id,
        user_id=ctx.user.id,
        action=action,
        title=title,
        summary=(
            f"{title}: {agreement.organization_name} — {agreement.specialty} "
            f"({agreement.doctor_count} médicos)"
        ),
        status=ActionProposalStatus.AWAITING_CONFIRMATION,
        payload={
            "agreement_id": str(agreement.id),
            "organization_id": str(agreement.organization_id),
            "organization_name": agreement.organization_name,
            "specialty": agreement.specialty,
            "current_status": agreement.status,
            "new_status": target_status.value,
            "doctor_count": agreement.doctor_count,
            "current_status_label": current_label,
            "new_status_label": new_label,
        },
    )
    ctx.db.add(proposal)
    await ctx.db.flush()

    return json.dumps(
        {
            "action_proposal_id": str(proposal.id),
            "action": action,
            "requires_confirmation": True,
            "message": "Propuesta lista. El usuario debe confirmar antes de aplicar el cambio.",
            "preview": proposal.payload,
        },
        ensure_ascii=False,
    )


async def _prepare_suspend_agreement(
    ctx: ToolContext,
    agreement_id: str | None = None,
    organization_query: str | None = None,
    specialty: str | None = None,
) -> str:
    return await _prepare_agreement_status(
        ctx,
        target_status=AgreementStatus.SUSPENDED,
        agreement_id=agreement_id,
        organization_query=organization_query,
        specialty=specialty,
    )


async def _prepare_activate_agreement(
    ctx: ToolContext,
    agreement_id: str | None = None,
    organization_query: str | None = None,
    specialty: str | None = None,
) -> str:
    return await _prepare_agreement_status(
        ctx,
        target_status=AgreementStatus.ACTIVE,
        agreement_id=agreement_id,
        organization_query=organization_query,
        specialty=specialty,
    )


ACTION_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="prepare_email",
        description=(
            "Prepara un email a una obra social o destinatario. "
            "NO lo envía: crea una propuesta que el usuario debe confirmar."
        ),
        parameters={
            "type": "object",
            "properties": {
                "organization_query": {
                    "type": "string",
                    "description": "Nombre de la obra social (ej. OSDE)",
                },
                "to": {"type": "string", "description": "Email destino si ya se conoce"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
        },
        kind="action",
        handler=_prepare_email,
    ),
    ToolSpec(
        name="prepare_suspend_agreement",
        description=(
            "Prepara la suspensión de un convenio. "
            "NO lo modifica: crea una propuesta para confirmación del usuario."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agreement_id": {"type": "string"},
                "organization_query": {"type": "string"},
                "specialty": {"type": "string"},
            },
        },
        kind="action",
        handler=_prepare_suspend_agreement,
    ),
    ToolSpec(
        name="prepare_activate_agreement",
        description=(
            "Prepara la reactivación de un convenio. "
            "NO lo modifica: crea una propuesta para confirmación del usuario."
        ),
        parameters={
            "type": "object",
            "properties": {
                "agreement_id": {"type": "string"},
                "organization_query": {"type": "string"},
                "specialty": {"type": "string"},
            },
        },
        kind="action",
        handler=_prepare_activate_agreement,
    ),
]
