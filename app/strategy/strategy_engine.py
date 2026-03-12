# app/strategy/strategy_engine.py

import logging
from enum import Enum
from typing import Optional
from pydantic import BaseModel

from app.core.context import AgentContext

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Enums — valores possíveis das decisões estratégicas
# ------------------------------------------------------------------

class NextAction(str, Enum):
    """
    Ação operacional a ser tomada após a qualificação do lead.

    HANDOFF_TO_HUMAN → encaminhar para especialista humano imediatamente
    NURTURE          → manter em fluxo de nutrição automática
    SCHEDULE_CONTACT → agendar contato futuro (fase 2)
    NONE             → nenhuma ação definida (fallback)
    """
    HANDOFF_TO_HUMAN = "HANDOFF_TO_HUMAN"
    NURTURE = "NURTURE"
    SCHEDULE_CONTACT = "SCHEDULE_CONTACT"
    NONE = "NONE"


class Priority(str, Enum):
    """
    Prioridade operacional do lead na fila de atendimento.
    """
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ------------------------------------------------------------------
# Schemas de saída — tipados e validados
# ------------------------------------------------------------------

class FollowUpConfig(BaseModel):
    """Configuração do follow-up automático."""
    enabled: bool
    delay_days: int
    reason: str


class StrategyResult(BaseModel):
    """
    Resultado da decisão estratégica do StrategyEngine.

    Separado da resposta ao cliente — o engine decide
    a ação operacional, não o conteúdo da mensagem.
    """
    trace_id: str
    lead_score: str
    goal: Optional[str]
    next_action: NextAction
    priority: Priority
    followup: Optional[FollowUpConfig]
    reasoning: str


# ------------------------------------------------------------------
# Regras de prioridade por goal
# ------------------------------------------------------------------

# Goals que elevam prioridade dentro da mesma temperatura
# Ex: HOT + LIMPAR_NOME → priority ainda HIGH, mas reasoning específico
# Na fase 2, pode diferenciar para URGENT dentro de HIGH
HIGH_PRIORITY_GOALS = {
    "LIMPAR_NOME",
    "NEGOCIAR_DIVIDAS",
    "FINANCIAMENTO",
}

MEDIUM_PRIORITY_GOALS = {
    "CREDITO_ALTO",
    "ALUGAR_IMOVEL",
}


class StrategyEngine:
    """
    Motor de decisão operacional do pipeline Eleva.

    Responsabilidades:
    - Definir a próxima ação (HANDOFF, NURTURE, etc.)
    - Definir prioridade na fila de atendimento
    - Configurar follow-up automático
    - Registrar raciocínio da decisão para auditoria

    NÃO modifica a resposta ao cliente.
    NÃO gera conteúdo de mensagem.
    NÃO conhece a lógica interna dos agentes.
    """

    @staticmethod
    def apply(
        lead_score: str,
        goal: Optional[str],
        sdr_result: Optional[str],
    ) -> StrategyResult:
        """
        Aplica as regras estratégicas com base na temperatura e objetivo.

        Args:
            lead_score: Temperatura do lead (HOT, WARM, COLD).
            goal: Objetivo identificado pelo GoalClassifierAgent.
            sdr_result: Resposta gerada pelo SDRAgent (não modificada aqui).

        Returns:
            StrategyResult com a decisão operacional completa.
        """
        logger.info(
            "strategy_engine_applying",
            extra={
                "lead_score": lead_score,
                "goal": goal,
            }
        )

        result = StrategyEngine._decide(lead_score, goal)

        logger.info(
            "strategy_engine_decided",
            extra={
                "lead_score": lead_score,
                "goal": goal,
                "next_action": result.next_action,
                "priority": result.priority,
                "reasoning": result.reasoning,
            }
        )

        return result

    @staticmethod
    def _decide(lead_score: str, goal: Optional[str]) -> StrategyResult:
        """
        Lógica central de decisão.

        Separada do método público para facilitar testes unitários
        e extensão futura (ex: adicionar regras por produto na fase 2).
        """
        score = (lead_score or "WARM").upper()
        goal_upper = (goal or "OUTRO").upper()

        # ------------------------------------------------------------------
        # HOT → encaminhar para humano imediatamente, prioridade alta
        # ------------------------------------------------------------------
        if score == "HOT":
            return StrategyResult(
                trace_id="",  # preenchido pelo Orchestrator
                lead_score=score,
                goal=goal,
                next_action=NextAction.HANDOFF_TO_HUMAN,
                priority=Priority.HIGH,
                followup=None,
                reasoning=(
                    f"Lead HOT com objetivo '{goal_upper}': alta intenção detectada. "
                    f"Encaminhamento imediato para especialista humano com prioridade máxima."
                ),
            )

        # ------------------------------------------------------------------
        # WARM → encaminhar para humano, prioridade baseada no goal
        # ------------------------------------------------------------------
        if score == "WARM":
            priority = (
                Priority.HIGH
                if goal_upper in HIGH_PRIORITY_GOALS
                else Priority.MEDIUM
            )

            return StrategyResult(
                trace_id="",
                lead_score=score,
                goal=goal,
                next_action=NextAction.HANDOFF_TO_HUMAN,
                priority=priority,
                followup=FollowUpConfig(
                    enabled=True,
                    delay_days=2,
                    reason=(
                        "Lead WARM: interesse real detectado. "
                        "Follow-up em 2 dias caso o especialista não consiga contato."
                    ),
                ),
                reasoning=(
                    f"Lead WARM com objetivo '{goal_upper}': interesse real mas sem urgência imediata. "
                    f"Prioridade {priority.value} baseada no tipo de objetivo."
                ),
            )

        # ------------------------------------------------------------------
        # COLD → nutrição automática, baixa prioridade
        # ------------------------------------------------------------------
        if score == "COLD":
            return StrategyResult(
                trace_id="",
                lead_score=score,
                goal=goal,
                next_action=NextAction.NURTURE,
                priority=Priority.LOW,
                followup=FollowUpConfig(
                    enabled=True,
                    delay_days=4,
                    reason=(
                        "Lead COLD: baixa intenção detectada. "
                        "Follow-up em 4 dias com conteúdo educativo sobre o produto."
                    ),
                ),
                reasoning=(
                    f"Lead COLD com objetivo '{goal_upper}': baixa intenção ou sem urgência. "
                    f"Encaminhado para nutrição automática com follow-up em 4 dias."
                ),
            )

        # ------------------------------------------------------------------
        # Fallback — score inválido ou não reconhecido
        # ------------------------------------------------------------------
        logger.warning(
            "strategy_engine_unknown_score",
            extra={"lead_score": lead_score, "goal": goal}
        )

        return StrategyResult(
            trace_id="",
            lead_score=score,
            goal=goal,
            next_action=NextAction.NONE,
            priority=Priority.LOW,
            followup=None,
            reasoning=(
                f"Score '{score}' não reconhecido. "
                f"Nenhuma ação definida — revisar manualmente."
            ),
        )