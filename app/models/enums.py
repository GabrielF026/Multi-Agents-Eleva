import enum
from enum import Enum


class LeadStatus(enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    HANDOFF = "HANDOFF"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


class Goal(enum.Enum):
    FINANCIAMENTO = "FINANCIAMENTO"
    CREDITO_ALTO = "CREDITO_ALTO"
    LIMPAR_NOME = "LIMPAR_NOME"
    NEGOCIAR_DIVIDAS = "NEGOCIAR_DIVIDAS"
    ALUGAR_IMOVEL = "ALUGAR_IMOVEL"
    OUTRO = "OUTRO"


class LeadScore(enum.Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class Priority(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class NextAction(Enum):
    HANDOFF_TO_HUMAN = "HANDOFF_TO_HUMAN"
    FOLLOWUP = "FOLLOWUP"
    NURTURE = "NURTURE"


class MessageSender(enum.Enum):
    CLIENT = "CLIENT"
    SYSTEM = "SYSTEM"


class ClassificationSource(enum.Enum):
    RULE = "RULE"
    LLM = "LLM"