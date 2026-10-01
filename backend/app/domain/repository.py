"""Contrato de acceso a datos de dominio.

Las tools del agente dependen de este Protocol, no de SQLAlchemy.
Para migrar a una DB/API real: implementá DomainRepository y registrala en factory.py.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.views import AgreementView, DoctorView, OrganizationView
from app.models.domain import AgreementStatus


class DomainRepository(Protocol):
    async def search_organizations(self, query: str, *, limit: int = 10) -> list[OrganizationView]:
        ...

    async def get_organization(self, organization_id: UUID) -> OrganizationView | None:
        ...

    async def search_agreements(
        self,
        *,
        organization_query: str | None = None,
        specialty: str | None = None,
        status: AgreementStatus | None = None,
        limit: int = 20,
    ) -> list[AgreementView]:
        ...

    async def get_agreement(self, agreement_id: UUID) -> AgreementView | None:
        ...

    async def set_agreement_status(
        self,
        agreement_id: UUID,
        status: AgreementStatus,
    ) -> AgreementView:
        ...

    async def search_doctors(
        self,
        *,
        query: str | None = None,
        specialty: str | None = None,
        agreement_status: AgreementStatus | None = None,
        limit: int = 20,
    ) -> list[DoctorView]:
        ...
