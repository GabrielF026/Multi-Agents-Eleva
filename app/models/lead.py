import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base
from app.models.enums import (
    LeadStatus,
    LeadScore,
    Goal,
    Priority,
)


class Lead(Base):
    __tablename__ = "leads"

    # ========================
    # Primary Key
    # ========================
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # ========================
    # Informações básicas
    # ========================
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    # ========================
    # Status e Classificação
    # ========================
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status"),
        default=LeadStatus.NEW,
        nullable=False
    )

    score: Mapped[LeadScore | None] = mapped_column(
        Enum(LeadScore, name="lead_score"),
        nullable=True
    )

    goal: Mapped[Goal | None] = mapped_column(
        Enum(Goal, name="lead_goal"),
        nullable=True
    )

    priority: Mapped[Priority | None] = mapped_column(
        Enum(Priority, name="lead_priority"),
        nullable=True
    )

    # ========================
    # Auditoria
    # ========================
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # ========================
    # Relacionamentos
    # ========================
    conversations = relationship(
        "Conversation",
        back_populates="lead",
        cascade="all, delete-orphan"
    )

    # ========================
    # Interesses (novo)
    # ========================
    interests = relationship(
        "LeadInterest",
        back_populates="lead",
        cascade="all, delete-orphan"
    )

    # ========================
    # State Machine
    # ========================
    ALLOWED_TRANSITIONS = {
        LeadStatus.NEW: [LeadStatus.CONTACTED],
        LeadStatus.CONTACTED: [
            LeadStatus.QUALIFIED,
            LeadStatus.CLOSED_LOST
        ],
        LeadStatus.QUALIFIED: [
            LeadStatus.HANDOFF,
            LeadStatus.CLOSED_LOST
        ],
        LeadStatus.HANDOFF: [
            LeadStatus.CLOSED_WON,
            LeadStatus.CLOSED_LOST
        ],
    }

    def update_status(self, new_status: LeadStatus):

        current_status = self.status

        if current_status not in self.ALLOWED_TRANSITIONS:
            raise ValueError(f"Status atual inválido: {current_status}")

        if new_status not in self.ALLOWED_TRANSITIONS[current_status]:
            raise ValueError(
                f"Transição inválida de {current_status} para {new_status}"
            )

        self.status = new_status

    # ========================
    # Aplicação da Estratégia
    # ========================
    def apply_strategy(
        self,
        lead_score: LeadScore,
        goal: Goal,
        priority: Priority,
        next_action: str,
    ):
        """
        Atualiza score, goal, prioridade e
        progride status respeitando a state machine.
        """

        # Atualiza atributos estratégicos
        self.score = lead_score
        self.goal = goal
        self.priority = priority

        # ==========================
        # Progressão automática MVP
        # ==========================

        if lead_score == LeadScore.HOT:

            if self.status == LeadStatus.NEW:
                self.update_status(LeadStatus.CONTACTED)

            if self.status == LeadStatus.CONTACTED:
                self.update_status(LeadStatus.QUALIFIED)

            if self.status == LeadStatus.QUALIFIED:
                self.update_status(LeadStatus.HANDOFF)

        elif lead_score == LeadScore.WARM:

            if self.status == LeadStatus.NEW:
                self.update_status(LeadStatus.CONTACTED)

            if self.status == LeadStatus.CONTACTED:
                self.update_status(LeadStatus.QUALIFIED)

        elif lead_score == LeadScore.COLD:

            if self.status == LeadStatus.NEW:
                self.update_status(LeadStatus.CONTACTED)