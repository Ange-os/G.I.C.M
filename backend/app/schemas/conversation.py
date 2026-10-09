from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.entities import (
    Channel,
    ConversationStatus,
    MessageDirection,
    SenderType,
)

HandlingMode = Literal["automatic", "human"]


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str
    name: str | None
    created_at: datetime
    picture: str | None = None
    username: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _pull_profile_from_metadata(cls, data: object) -> object:
        if hasattr(data, "metadata_"):
            meta = getattr(data, "metadata_", None) or {}
            return {
                "id": data.id,
                "phone": data.phone,
                "name": data.name,
                "created_at": data.created_at,
                "picture": meta.get("picture") if isinstance(meta, dict) else None,
                "username": (
                    (meta.get("instagram_username") or meta.get("username"))
                    if isinstance(meta, dict)
                    else None
                ),
            }
        if isinstance(data, dict):
            meta = data.get("metadata_") or data.get("metadata") or {}
            if isinstance(meta, dict):
                return {
                    **data,
                    "picture": data.get("picture") or meta.get("picture"),
                    "username": data.get("username")
                    or meta.get("instagram_username")
                    or meta.get("username"),
                }
        return data


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    direction: MessageDirection
    sender_type: SenderType
    content: str | None
    media_url: str | None
    payload: dict
    external_id: str | None
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    contact_id: UUID
    channel: Channel
    status: ConversationStatus
    ycloud_phone_number_id: str | None
    assigned_agent_id: UUID | None
    metadata: dict = Field(alias="metadata_")
    created_at: datetime
    updated_at: datetime
    contact: ContactRead | None = None
    tags: list[TagRead] = []
    handling_mode: HandlingMode = "automatic"


class ConversationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_id: UUID
    channel: Channel
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    contact: ContactRead | None = None
    tags: list[TagRead] = []
    whatsapp_provider: str | None = None
    handling_mode: HandlingMode = "automatic"


class MetaWebhookResponse(BaseModel):
    ok: bool
    processed: int = 0
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    duplicate: bool = False


class WhatsAppProvidersStatus(BaseModel):
    default_provider: str
    providers: list[dict]


class TagsMutation(BaseModel):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


class N8nInboundMessage(BaseModel):
    sender_type: SenderType = SenderType.BOT
    content: str | None = None
    media_url: str | None = None
    payload: dict = Field(default_factory=dict)


class N8nInboundRequest(BaseModel):
    conversation_id: UUID
    tags: TagsMutation | None = None
    message: N8nInboundMessage | None = None
    status: ConversationStatus | None = None
    send_whatsapp: bool = False


class N8nInboundResponse(BaseModel):
    conversation: ConversationRead
    message: MessageRead | None = None


class YCloudWebhookResponse(BaseModel):
    ok: bool
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    duplicate: bool = False


class AgentMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    send_whatsapp: bool = True


class ConversationActionResponse(BaseModel):
    conversation: ConversationRead
    message: MessageRead | None = None
