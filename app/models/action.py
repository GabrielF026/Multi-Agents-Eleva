import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base
from app.models.enums import Priority, NextAction


class Action(Base):
    __tablename__ = "actions"

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

    next_action: Mapped[NextAction] = mapped_column(
        Enum(NextAction, name="next_action_enum"),
        nullable=False
    )

    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="action_priority"),
        nullable=False
    )

    followup_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    followup_delay_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )