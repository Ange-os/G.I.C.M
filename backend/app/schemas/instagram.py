from uuid import UUID

from pydantic import BaseModel, Field


class InstagramN8nInbound(BaseModel):
    """Evento normalizado desde el workflow n8n de Instagram."""

    channel: str = "instagram"
    sender_id: str = Field(min_length=1, alias="senderId")
    recipient_id: str | None = Field(default=None, alias="recipientId")
    external_id: str | None = Field(default=None, alias="external_id")
    mid: str | None = None
    text: str | None = None
    timestamp: str | None = None
    is_echo: bool = Field(default=False, alias="isEcho")
    contact_name: str | None = Field(default=None, alias="contactName")

    model_config = {"populate_by_name": True}

    def resolved_external_id(self) -> str | None:
        value = self.external_id or self.mid
        return value.strip() if value else None


class InstagramWebhookResponse(BaseModel):
    ok: bool
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    duplicate: bool = False
    skipped: bool = False
    skip_reason: str | None = None
