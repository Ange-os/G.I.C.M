"""Datos de simulacro para un círculo médico / obras sociales."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.local_repository import count_organizations
from app.models.domain import Agreement, AgreementDoctor, AgreementStatus, Doctor, Organization

logger = logging.getLogger(__name__)


async def seed_domain_demo(db: AsyncSession) -> None:
    if await count_organizations(db) > 0:
        return

    osde = Organization(
        name="OSDE",
        short_name="OSDE",
        email="contacto@osde-demo.local",
        phone="+54 11 4000-1000",
        notes="Obra social demo — datos ficticios",
    )
    pami = Organization(
        name="PAMI",
        short_name="PAMI",
        email="convenios@pami-demo.local",
        phone="+54 11 4000-2000",
        notes="Obra social demo — datos ficticios",
    )
    swiss = Organization(
        name="Swiss Medical",
        short_name="Swiss",
        email="medicos@swiss-demo.local",
        phone="+54 11 4000-3000",
        notes="Obra social demo — datos ficticios",
    )
    db.add_all([osde, pami, swiss])
    await db.flush()

    doctors = [
        Doctor(full_name="Ana Gómez", specialty="Cardiología", license_number="MN-1001"),
        Doctor(full_name="Bruno Pérez", specialty="Cardiología", license_number="MN-1002"),
        Doctor(full_name="Carla Ruiz", specialty="Pediatría", license_number="MN-1003"),
        Doctor(full_name="Diego Soto", specialty="Pediatría", license_number="MN-1004"),
        Doctor(full_name="Elena Vargas", specialty="Traumatología", license_number="MN-1005"),
        Doctor(full_name="Facundo Díaz", specialty="Traumatología", license_number="MN-1006"),
        Doctor(full_name="Gisela López", specialty="Clínica Médica", license_number="MN-1007"),
        Doctor(full_name="Hernán Castro", specialty="Clínica Médica", license_number="MN-1008"),
        Doctor(full_name="Irene Molina", specialty="Cardiología", license_number="MN-1009"),
        Doctor(full_name="Julián Rojas", specialty="Pediatría", license_number="MN-1010"),
    ]
    db.add_all(doctors)
    await db.flush()

    by_specialty: dict[str, list[Doctor]] = {}
    for doctor in doctors:
        by_specialty.setdefault(doctor.specialty, []).append(doctor)

    agreements_spec = [
        (osde, "Cardiología", AgreementStatus.ACTIVE),
        (osde, "Pediatría", AgreementStatus.ACTIVE),
        (pami, "Cardiología", AgreementStatus.ACTIVE),
        (pami, "Traumatología", AgreementStatus.SUSPENDED),
        (swiss, "Clínica Médica", AgreementStatus.ACTIVE),
        (swiss, "Cardiología", AgreementStatus.ACTIVE),
    ]

    for organization, specialty, status in agreements_spec:
        agreement = Agreement(
            organization_id=organization.id,
            specialty=specialty,
            status=status,
            notes=f"Convenio demo {organization.short_name} — {specialty}",
        )
        db.add(agreement)
        await db.flush()
        for doctor in by_specialty.get(specialty, [])[:3]:
            db.add(AgreementDoctor(agreement_id=agreement.id, doctor_id=doctor.id))

    await db.flush()
    logger.info("Dominio demo sembrado: 3 obras sociales, 6 convenios, 10 médicos")
