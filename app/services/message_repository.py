from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, conversation_id, sender, content):
        message = Message(
            conversation_id=conversation_id,
            sender=sender,
            content=content
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    # 🔹 Última mensagem (controle de duplicidade)
    async def get_last_message_by_conversation(self, conversation_id):
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(1)
        )

        return result.scalar_one_or_none()

    # 🔹 Histórico (contexto LLM)
    async def get_last_messages_by_conversation(
        self,
        conversation_id,
        limit: int = 10
    ):
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )

        messages = result.scalars().all()

        # retorna em ordem cronológica correta
        return list(reversed(messages))