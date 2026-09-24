from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Channel, Conversation, Message, MessageDirection, SenderType
from app.services.conversation import create_message, get_conversation_with_relations
from app.services.ycloud_outbound import YCloudError, send_whatsapp_text


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
        try:
            ycloud_response = await send_whatsapp_text(
                to=conversation.contact.phone,
                text=content,
            )
            message.payload = {"ycloud": ycloud_response}
            if ycloud_response.get("id"):
                message.external_id = str(ycloud_response["id"])
        except YCloudError as exc:
            message.payload = {"ycloud_error": str(exc)}

    await db.flush()

    conversation = await get_conversation_with_relations(db, conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found after save")

    return conversation, message
