from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class XiaWebInbound(BaseModel):
    """Evento espejado desde xIA.ar al Inbox (canal web)."""

    model_config = ConfigDict(populate_by_name=True)

    sender_id: str = Field(min_length=1, alias="senderId")
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    text: str | None = None
    role: str = "contact"
    external_conversation_id: str | None = Field(default=None, alias="externalConversationId")
    external_message_id: str | None = Field(default=None, alias="externalMessageId")
    source: str | None = "xia.ar"


class XiaWebhookResponse(BaseModel):
    ok: bool
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    duplicate: bool = False
