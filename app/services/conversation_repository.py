from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


class ConversationRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_latest_by_lead(self, lead_id):
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.lead_id == lead_id)
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, lead_id):
        conversation = Conversation(lead_id=lead_id)
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation