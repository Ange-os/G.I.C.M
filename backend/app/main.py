from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import Base, async_session, engine
from app.domain.seed import seed_domain_demo
from app.models import domain as _domain_models  # noqa: F401 — registra tablas en metadata
from app.routers import (
    assistant,
    auth,
    conversations,
    tools,
    webhooks_instagram,
    webhooks_meta,
    webhooks_n8n,
    webhooks_ycloud,
)
from app.services.conversation import seed_default_tags
from app.services.users import seed_default_users
from app.services.events import close_redis, get_redis

logger = logging.getLogger(__name__)


async def _ensure_instagram_channel_enum(conn) -> None:
    """Agrega el valor 'instagram' al enum PostgreSQL si aún no existe."""
    try:
        await conn.execute(text("ALTER TYPE channel ADD VALUE IF NOT EXISTS 'instagram'"))
    except Exception as exc:  # noqa: BLE001
        # En DBs nuevas create_all ya puede incluirlo; ignorar conflictos.
        logger.debug("channel enum instagram: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_instagram_channel_enum(conn)

    async with async_session() as session:
        await seed_default_tags(session)
        await seed_default_users(session)
        await seed_domain_demo(session)
        await session.commit()

    try:
        await get_redis()
    except Exception:
        pass

    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="Conversa Platform API",
    description="Conversación embebible: WhatsApp (YCloud/Meta), Instagram (n8n) y agente",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(assistant.router)
app.include_router(tools.router)
app.include_router(webhooks_ycloud.router)
app.include_router(webhooks_meta.router)
app.include_router(webhooks_n8n.router)
app.include_router(webhooks_instagram.router)
app.include_router(conversations.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
