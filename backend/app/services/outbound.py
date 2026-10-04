from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Channel, Conversation, Message, MessageDirection, SenderType
from app.services.conversation import create_message, get_conversation_with_relations
from app.whatsapp.base import WhatsAppProviderError
from app.whatsapp.conversation_provider import get_conversation_provider
from app.whatsapp.factory import get_whatsapp_provider


async def send_conversation_reply(
    db: AsyncSession,
    conversation_id: UUID,
    *,
    content: str,
    sender_type: SenderType,
    send_whatsapp: bool = False,
) -> tuple[Conversation, Message]:
    conversation = await get_conversation_with_relations(db, conversation_id)
    if not conversation:
        raise ValueError("Conversation not found")

    message = await create_message(
        db,
        conversation,
        direction=MessageDirection.OUTBOUND,
        sender_type=sender_type,
        content=content,
        payload={},
    )
    if message is None:
        raise ValueError("Message could not be created")

    if send_whatsapp and conversation.channel == Channel.WHATSAPP and content:
        provider_name = get_conversation_provider(conversation)
        provider = get_whatsapp_provider(provider_name)
        phone_number_id = (conversation.metadata_ or {}).get("phone_number_id")
        if not phone_number_id and conversation.ycloud_phone_number_id:
            phone_number_id = conversation.ycloud_phone_number_id
        try:
            result = await provider.send_text(
                to=conversation.contact.phone,
                text=content,
                phone_number_id=str(phone_number_id) if phone_number_id else None,
            )
            message.payload = {
                "provider": provider_name,
                provider_name: result.raw,
            }
            if result.external_id:
                message.external_id = result.external_id
        except WhatsAppProviderError as exc:
            message.payload = {
                "provider": provider_name,
                f"{provider_name}_error": str(exc),
            }

    await db.flush()

    conversation = await get_conversation_with_relations(db, conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found after save")

    return conversation, message
