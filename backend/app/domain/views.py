"""Vistas de negocio para el agente.

Representaciones limpias: el LLM solo ve estos campos, no el esquema SQL.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrganizationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    short_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class AgreementView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    organization_name: str
    specialty: str
    status: str
    doctor_count: int = 0
    notes: str | None = None
    updated_at: datetime | None = None


class DoctorView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    specialty: str
    license_number: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool = True
    agreement_ids: list[UUID] = []
