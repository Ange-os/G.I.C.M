from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import (
    Channel,
    ConversationStatus,
    MessageDirection,
    SenderType,
)


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str
    name: str | None
    created_at: datetime


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
