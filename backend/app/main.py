from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, async_session, engine
from app.routers import assistant, auth, conversations, tools, webhooks_n8n, webhooks_ycloud
from app.services.conversation import seed_default_tags
from app.services.users import seed_default_users
from app.services.events import close_redis, get_redis


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await seed_default_tags(session)
        await seed_default_users(session)
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
    description="Módulo de conversación embebible con integración YCloud y n8n",
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
app.include_router(webhooks_n8n.router)
app.include_router(conversations.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
