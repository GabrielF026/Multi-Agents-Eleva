from sqlalchemy.ext.asyncio import AsyncSession
from app.models.classification import Classification
from app.models.enums import ClassificationSource


class ClassificationRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, lead_id, goal, source: ClassificationSource):
        classification = Classification(
            lead_id=lead_id,
            goal=goal,
            source=source,
        )
        self.db.add(classification)
        await self.db.commit()
        await self.db.refresh(classification)
        return classification