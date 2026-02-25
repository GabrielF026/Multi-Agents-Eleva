from sqlalchemy.ext.asyncio import AsyncSession
from app.models.action import Action


class ActionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        lead_id,
        next_action,
        priority,
        followup_enabled: bool,
        followup_delay_days: int | None
    ):
        action = Action(
            lead_id=lead_id,
            next_action=next_action,
            priority=priority,
            followup_enabled=followup_enabled,
            followup_delay_days=followup_delay_days,
        )
        self.db.add(action)
        await self.db.commit()
        await self.db.refresh(action)
        return action