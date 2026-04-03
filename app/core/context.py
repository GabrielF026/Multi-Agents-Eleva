# app/core/context.py

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class LeadData(BaseModel):
    """
    Dados brutos do lead recebidos pela API.
    Imutável após criação — representa o input original.
    """
    message: str
    history: list[dict] = Field(default_factory=list)
    is_repeated: bool = False
    current_goal: Optional[str] = None
    current_lead_score: Optional[str] = None  # HOT / WARM / COLD da mensagem anterior


class AgentContext(BaseModel):
    """
    Objeto de estado que percorre todo o pipeline de agentes.
    """

    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="ID único por requisição. Usado em todos os logs."
    )

    lead: LeadData

    goal: Optional[str] = Field(
        default=None,
        description="Objetivo classificado pelo GoalClassifierAgent"
    )
    goal_source: Optional[str] = Field(
        default=None,
        description="Como o goal foi determinado: 'rule', 'llm' ou 'current_goal'"
    )
    lead_score: Optional[str] = Field(
        default=None,
        description="Temperatura do lead: HOT, WARM ou COLD"
    )
    lead_score_source: Optional[str] = Field(
        default=None,
        description="Como o score foi determinado: 'rule', 'llm' ou 'preserved'"
    )
    sdr_response: Optional[str] = Field(
        default=None,
        description="Resposta gerada pelo SDRAgent"
    )
    strategy: Optional[dict] = Field(
        default=None,
        description="Estratégia operacional definida pelo StrategyEngine"
    )
    product_key: Optional[str] = Field(
        default=None,
        description="Key do produto travado para esta conversa"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Lista de erros não críticos ocorridos durante o pipeline"
    )
    fast_forward_response: Optional[str] = Field(
        default=None,
        description="Pula as gerações de IA seguintes para responder uma trava rápida (Ex: Handoff Imediato ou Ofensas) poupando LLM."
    )

    class Config:
        frozen = True