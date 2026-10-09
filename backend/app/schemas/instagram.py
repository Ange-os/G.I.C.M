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
    # contact = usuario; bot/agent = respuesta de la página (espejo en Inbox)
    role: str | None = None
    contact_name: str | None = Field(default=None, alias="contactName")
    # Perfil Graph (n8n: Obtener Perfil → name / username / profile_pic | profilePic)
    name: str | None = None
    username: str | None = None
    profile_pic: str | None = Field(default=None, alias="profilePic")

    model_config = {"populate_by_name": True}

    def resolved_external_id(self) -> str | None:
        value = self.external_id or self.mid
        return value.strip() if value else None

    def resolved_display_name(self) -> str | None:
        for value in (self.contact_name, self.name, self.username):
            if value and str(value).strip():
                return str(value).strip()
        return None

    def resolved_username(self) -> str | None:
        if self.username and self.username.strip():
            return self.username.strip().lstrip("@")
        return None

    def resolved_profile_pic(self) -> str | None:
        if self.profile_pic and self.profile_pic.strip():
            return self.profile_pic.strip()
        return None

    def is_page_outbound(self) -> bool:
        """Respuesta de la página / Agent (echo) hacia el usuario."""
        role = (self.role or "").strip().lower()
        if role in {"bot", "agent"}:
            return True
        return bool(self.is_echo)


class InstagramWebhookResponse(BaseModel):
    ok: bool
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    duplicate: bool = False
    skipped: bool = False
    skip_reason: str | None = None
