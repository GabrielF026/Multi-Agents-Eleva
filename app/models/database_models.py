from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from app.infrastructure.database import Base

class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    MARKETING_NURTURE = "MARKETING_NURTURE" # COLD - Nutricao
    HANDOFF_PENDING = "HANDOFF_PENDING" # WARM - Vendedor regular
    HANDOFF_PENDING_URGENT = "HANDOFF_PENDING_URGENT" # HOT - Prioridade absoluta
    CONSOLIDATED = "CONSOLIDATED" # Vendido / Resolvido
    DEAD = "DEAD" # Lead perdido

class Lead(Base):
    """
    Tabela segura armazenando dados persistentes do Lead de forma privada no DB.
    """
    __tablename__ = "leads"

    # WhatsApp / Telefone age como identificador único principal 
    phone_number = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=True) # Começa NULL, IA tenta extrair depois
    
    current_goal = Column(String(100), nullable=True)
    current_score = Column(String(50), default="UNKNOWN")  # HOT/WARM/COLD
    
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW)
    notes = Column(Text, nullable=True) # Observacoes pro vendedor
    
    is_repeated = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_interaction = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source = Column(String(50), default="whatsapp") # Canal de origem: whatsapp ou instagram
    
    messages = relationship("Interaction", back_populates="lead", cascade="all, delete-orphan")


class Interaction(Base):
    """
    Guarda o histórico de bate papo blindado contra vazamentos. Referencia o Lead.
    """
    __tablename__ = "interactions"

    id = Column(String(36), primary_key=True) # trace_id original ou UUID se for longo
    phone_number = Column(String(50), ForeignKey("leads.phone_number"), index=True)
    
    role = Column(String(50)) # 'user' ou 'assistant' ou 'system'
    content = Column(Text)
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    lead = relationship("Lead", back_populates="messages")
