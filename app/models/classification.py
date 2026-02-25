import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base
from app.models.enums import Goal, ClassificationSource


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id"),
        nullable=False,
        index=True
    )

    goal: Mapped[Goal] = mapped_column(
        Enum(Goal, name="classification_goal"),
        nullable=False
    )

    source: Mapped[ClassificationSource] = mapped_column(
        Enum(ClassificationSource, name="classification_source"),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )