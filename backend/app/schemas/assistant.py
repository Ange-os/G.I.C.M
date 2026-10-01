from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import AssistantRole


class AssistantStatusRead(BaseModel):
    configured: bool
    model: str
    domain_data_source: str = "local"
    agent_enabled: bool = True


class CatalogActionRead(BaseModel):
    id: str
    title: str
    description: str
    starter_message: str
    category: str


class AssistantThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ActionProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    message_id: UUID | None = None
    action: str
    title: str
    summary: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error_message: str | None = None
    requires_confirmation: bool = True
    created_at: datetime
    updated_at: datetime


class AssistantMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    role: AssistantRole
    content: str
    created_at: datetime
    action: ActionProposalRead | None = None


class AssistantMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class AssistantSendResponse(BaseModel):
    thread: AssistantThreadRead
    messages: list[AssistantMessageRead]


class ActionConfirmBody(BaseModel):
    to: str | None = None
    subject: str | None = None
    body: str | None = None


class ActionConfirmResponse(BaseModel):
    proposal: ActionProposalRead
    message: AssistantMessageRead
    messages: list[AssistantMessageRead]


class ActionCancelResponse(BaseModel):
    proposal: ActionProposalRead
