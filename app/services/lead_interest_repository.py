from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_interest import LeadInterest
from app.models.enums import Goal


class LeadInterestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================
    # Criar novo interesse
    # ==========================
    async def create(self, lead_id, goal: Goal) -> LeadInterest:
        interest = LeadInterest(
            lead_id=lead_id,
            goal=goal,
        )

        self.db.add(interest)
        await self.db.commit()
        await self.db.refresh(interest)

        return interest

    # ==========================
    # Verificar se já existe
    # ==========================
    async def exists(self, lead_id, goal: Goal) -> bool:
        result = await self.db.execute(
            select(LeadInterest).where(
                LeadInterest.lead_id == lead_id,
                LeadInterest.goal == goal,
            )
        )

        return result.scalar_one_or_none() is not None

    # ==========================
    # Listar interesses do lead
    # ==========================
    async def list_by_lead(self, lead_id) -> List[LeadInterest]:
        result = await self.db.execute(
            select(LeadInterest).where(
                LeadInterest.lead_id == lead_id
            )
        )

        return result.scalars().all()