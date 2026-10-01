"""Implementación local sobre las tablas de simulacro en Postgres."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.views import AgreementView, DoctorView, OrganizationView
from app.models.domain import Agreement, AgreementDoctor, AgreementStatus, Doctor, Organization


class LocalDomainRepository:
    """Lee/escribe el dominio demo en la misma DB de Conversa."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def search_organizations(self, query: str, *, limit: int = 10) -> list[OrganizationView]:
        text = (query or "").strip()
        stmt = select(Organization).order_by(Organization.name.asc()).limit(limit)
        if text:
            pattern = f"%{text}%"
            stmt = stmt.where(
                or_(
                    Organization.name.ilike(pattern),
                    Organization.short_name.ilike(pattern),
                )
            )
        rows = list((await self._db.scalars(stmt)).all())
        return [OrganizationView.model_validate(row) for row in rows]

    async def get_organization(self, organization_id: UUID) -> OrganizationView | None:
        row = await self._db.get(Organization, organization_id)
        return OrganizationView.model_validate(row) if row else None

    async def search_agreements(
        self,
        *,
        organization_query: str | None = None,
        specialty: str | None = None,
        status: AgreementStatus | None = None,
        limit: int = 20,
    ) -> list[AgreementView]:
        stmt = (
            select(Agreement)
            .options(selectinload(Agreement.organization), selectinload(Agreement.doctors))
            .join(Organization)
            .order_by(Organization.name.asc(), Agreement.specialty.asc())
            .limit(limit)
        )
        if organization_query and organization_query.strip():
            pattern = f"%{organization_query.strip()}%"
            stmt = stmt.where(
                or_(
                    Organization.name.ilike(pattern),
                    Organization.short_name.ilike(pattern),
                )
            )
        if specialty and specialty.strip():
            stmt = stmt.where(Agreement.specialty.ilike(f"%{specialty.strip()}%"))
        if status is not None:
            stmt = stmt.where(Agreement.status == status)

        rows = list((await self._db.scalars(stmt)).all())
        return [self._to_agreement_view(row) for row in rows]

    async def get_agreement(self, agreement_id: UUID) -> AgreementView | None:
        stmt = (
            select(Agreement)
            .where(Agreement.id == agreement_id)
            .options(selectinload(Agreement.organization), selectinload(Agreement.doctors))
        )
        row = await self._db.scalar(stmt)
        return self._to_agreement_view(row) if row else None

    async def set_agreement_status(
        self,
        agreement_id: UUID,
        status: AgreementStatus,
    ) -> AgreementView:
        """Actualiza el estado y devuelve una View cargada de nuevo (async-safe).

        Tras un flush, columnas con ``onupdate`` server-side pueden expirarse y
        disparar lazy IO síncrono (MissingGreenlet). Por eso no serializamos el
        mismo ORM instance: re-leemos con ``get_agreement``.
        """
        row = await self._db.get(Agreement, agreement_id)
        if not row:
            raise LookupError("Convenio no encontrado")

        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        await self._db.flush()

        updated = await self.get_agreement(agreement_id)
        if not updated:
            raise LookupError("Convenio no encontrado tras actualizar")
        return updated

    async def search_doctors(
        self,
        *,
        query: str | None = None,
        specialty: str | None = None,
        agreement_status: AgreementStatus | None = None,
        limit: int = 20,
    ) -> list[DoctorView]:
        stmt = select(Doctor).order_by(Doctor.full_name.asc()).limit(limit)
        if query and query.strip():
            stmt = stmt.where(Doctor.full_name.ilike(f"%{query.strip()}%"))
        if specialty and specialty.strip():
            stmt = stmt.where(Doctor.specialty.ilike(f"%{specialty.strip()}%"))
        if agreement_status is not None:
            stmt = (
                stmt.join(AgreementDoctor)
                .join(Agreement)
                .where(Agreement.status == agreement_status)
                .distinct()
            )

        rows = list((await self._db.scalars(stmt)).all())
        result: list[DoctorView] = []
        for doctor in rows:
            link_ids = list(
                (
                    await self._db.scalars(
                        select(AgreementDoctor.agreement_id).where(
                            AgreementDoctor.doctor_id == doctor.id
                        )
                    )
                ).all()
            )
            result.append(
                DoctorView(
                    id=doctor.id,
                    full_name=doctor.full_name,
                    specialty=doctor.specialty,
                    license_number=doctor.license_number,
                    email=doctor.email,
                    phone=doctor.phone,
                    is_active=doctor.is_active,
                    agreement_ids=link_ids,
                )
            )
        return result

    @staticmethod
    def _to_agreement_view(row: Agreement) -> AgreementView:
        return AgreementView(
            id=row.id,
            organization_id=row.organization_id,
            organization_name=row.organization.name if row.organization else "",
            specialty=row.specialty,
            status=row.status.value,
            doctor_count=len(row.doctors or []),
            notes=row.notes,
            updated_at=row.updated_at,
        )


async def count_organizations(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(Organization)) or 0)
