from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.enums import LeadStatus


class LeadRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Lead | None:
        result = await self.db.execute(
            select(Lead).where(Lead.email == email)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        name: str | None,
        phone: str | None
    ) -> Lead:

        lead = Lead(
            email=email,
            name=name,
            phone=phone,
            status=LeadStatus.NEW,
        )

        self.db.add(lead)
        await self.db.commit()
        await self.db.refresh(lead)

        return lead

    async def save(self, lead: Lead) -> Lead:
        await self.db.commit()
        await self.db.refresh(lead)
        return lead