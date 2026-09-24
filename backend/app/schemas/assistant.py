from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.entities import AssistantRole


class AssistantStatusRead(BaseModel):
    configured: bool
    model: str


class AssistantThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class AssistantMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    role: AssistantRole
    content: str
    created_at: datetime


class AssistantMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class AssistantSendResponse(BaseModel):
    thread: AssistantThreadRead
    messages: list[AssistantMessageRead]
