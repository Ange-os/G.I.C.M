"""Factory del repository de dominio.

Cambio de fuente de datos:
  DOMAIN_DATA_SOURCE=local     → tablas simulacro (default)
  DOMAIN_DATA_SOURCE=external  → implementar ExternalDomainRepository y activarlo acá
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.local_repository import LocalDomainRepository
from app.domain.repository import DomainRepository


def get_domain_repository(db: AsyncSession) -> DomainRepository:
    source = (settings.domain_data_source or "local").strip().lower()
    if source == "local":
        return LocalDomainRepository(db)
    if source == "external":
        raise NotImplementedError(
            "DOMAIN_DATA_SOURCE=external aún no está implementado. "
            "Creá ExternalDomainRepository y registralo en app.domain.factory."
        )
    raise ValueError(f"DOMAIN_DATA_SOURCE desconocido: {source}")
