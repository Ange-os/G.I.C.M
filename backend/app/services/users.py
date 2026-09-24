import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entities import User, UserRole

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user.id), "role": user.role.value, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.strip().lower()))


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def _seed_user(
    db: AsyncSession,
    *,
    email: str | None,
    password: str | None,
    name: str,
    role: UserRole,
) -> None:
    if not email or not password:
        return

    normalized = email.strip().lower()
    existing = await get_user_by_email(db, normalized)
    if existing:
        return

    db.add(
        User(
            email=normalized,
            name=name,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
    )
    logger.info("Usuario inicial creado: %s (%s)", normalized, role.value)


async def seed_default_users(db: AsyncSession) -> None:
    await _seed_user(
        db,
        email=settings.admin_email,
        password=settings.admin_password,
        name=settings.admin_name,
        role=UserRole.ADMIN,
    )
    await _seed_user(
        db,
        email=settings.consejo_email,
        password=settings.consejo_password,
        name=settings.consejo_name,
        role=UserRole.CONSEJO,
    )
