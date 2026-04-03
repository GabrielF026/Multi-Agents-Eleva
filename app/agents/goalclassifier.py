# app/agents/goalclassifier.py

import unicodedata
import logging
from typing import Optional
from pydantic import BaseModel

from app.core.base_agent import BaseAgent
from app.core.context import AgentContext
from app.core.llm_provider import LLMProviderInterface

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Schema de saída do LLM — structured output
# ------------------------------------------------------------------

class GoalClassification(BaseModel):
    goal: str
    confidence: str
    reasoning: str


# ------------------------------------------------------------------
# Agente
# ------------------------------------------------------------------

class GoalClassifierAgent(BaseAgent):
    """
    Classifica o objetivo principal do lead.

    Fluxo de decisão (em ordem de prioridade):
    1. Se current_goal existir → preserva (não reclassifica)
    2. Regras por keywords → sem custo LLM
    3. Fallback LLM com structured output
    """

    VALID_GOALS = {
        "FINANCIAMENTO",
        "CREDITO_ALTO",
        "ALUGAR_IMOVEL",
        "NEGOCIAR_DIVIDAS",
        "LIMPAR_NOME",
        "OFF_TOPIC",
        "OUTRO",
    }

    _RULES: list[tuple[list[str], str]] = [
        (
            ["limpar nome", "limpa nome", "nome sujo", "serasa", "spc",
             "negativado", "negativada", "nome negativado", "tirar restricao",
             "limpar restricao", "nome limpo", "restricao no nome",
             "tirar restrição", "limpar restrição", "restrição no nome"],
            "LIMPAR_NOME",
        ),
        (
            ["negociar divida", "negociar dívida", "parcelar divida",
             "parcelar dívida", "renegociar", "acordo com credor",
             "quitar divida", "quitar dívida", "limpar dividas", "limpar dívidas"],
            "NEGOCIAR_DIVIDAS",
        ),
        (
            ["financiamento", "financiar imovel", "financiar imóvel",
             "financiar casa", "financiar apartamento", "credito imobiliario",
             "crédito imobiliário", "casa propria", "casa própria",
             "minha casa minha vida", "financiamento bancario"],
            "FINANCIAMENTO",
        ),
        (
            ["credito alto", "crédito alto", "limite alto", "emprestimo alto",
             "empréstimo alto", "credito pessoal", "crédito pessoal",
             "credito consignado", "crédito consignado", "emprestimo",
             "empréstimo", "precisar de credito", "precisar de crédito"],
            "CREDITO_ALTO",
        ),
        (
            ["alugar imovel", "alugar imóvel", "alugar apartamento",
             "alugar casa", "locacao", "locação", "aluguel",
             "fiador", "garantia de aluguel"],
            "ALUGAR_IMOVEL",
        ),
    ]

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(
            llm_provider=llm_provider,
            name="GoalClassifierAgent",
            description=(
                "Classifica o objetivo do lead. "
                "Preserva current_goal quando disponível."
            ),
            version="1.0.0",
        )

    async def run(self, context: AgentContext) -> AgentContext:
        self.log_start(context)

        # Removido o Bloqueio Absoluto do current_goal para permitir pivôs e mudanças de assunto reais.
        try:
            # ----------------------------------------------------------
            # PRIORIDADE 2: Regras por keywords
            # ----------------------------------------------------------
            rule_goal = self._classify_by_rules(context.lead.message)

            if rule_goal:
                self.logger.info(
                    "goal_classified_by_rule",
                    extra={
                        "trace_id": context.trace_id,
                        "goal": rule_goal,
                        "message_preview": context.lead.message[:60],
                    },
                )
                self.log_success(context)
                return context.model_copy(update={
                    "goal": rule_goal,
                    "goal_source": "rule",
                })

            # ----------------------------------------------------------
            # PRIORIDADE 3: Fallback LLM
            # ----------------------------------------------------------
            llm_goal = await self._classify_by_llm(context)
            
            # ----------------------------------------------------------
            # VERIFICAÇÃO DE TOXICIDADE / LIXO
            # ----------------------------------------------------------
            if llm_goal == "OFF_TOPIC":
                self.logger.warning("goal_classifier_off_topic_detected", extra={"trace_id": context.trace_id})
                self.log_success(context)
                return context.model_copy(update={
                    "goal": "OUTRO",
                    "goal_source": "llm",
                    "lead_score": "COLD",
                    "fast_forward_response": "Acho que não entendi. O nosso WhatsApp atende apenas dúvidas sobre linhas de crédito e renegociação. Posso te ajudar com isso?"
                })

            self.logger.info(
                "goal_classifier_llm_fallback",
                extra={
                    "trace_id": context.trace_id,
                    "goal": llm_goal,
                    "message_preview": context.lead.message[:60],
                },
            )
            self.log_success(context)
            return context.model_copy(update={
                "goal": llm_goal,
                "goal_source": "llm",
            })

        except Exception as e:
            updated = self.register_error(context, e)
            self.logger.error(
                "goal_classifier_error",
                extra={
                    "trace_id": context.trace_id,
                    "error": str(e),
                },
            )
            return updated.model_copy(update={
                "goal": "OUTRO",
                "goal_source": "fallback_error",
            })

    def _classify_by_rules(self, message: str) -> Optional[str]:
        normalized = self._normalize(message)
        for keywords, goal in self._RULES:
            for keyword in keywords:
                if self._normalize(keyword) in normalized:
                    return goal
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        return unicodedata.normalize("NFKD", text.lower()).encode(
            "ascii", "ignore"
        ).decode("ascii")

    async def _classify_by_llm(self, context: AgentContext) -> str:
        history_summary = self._summarize_history(context.lead.history)

        prompt = f"""Você é um classificador de intenção de leads para a Eleva,
empresa especializada em crédito e recuperação financeira.

## GOALS POSSÍVEIS
- FINANCIAMENTO: quer financiar imóvel, carro ou bem
- CREDITO_ALTO: quer crédito, empréstimo ou aumento de limite
- ALUGAR_IMOVEL: quer alugar imóvel mas tem restrição
- NEGOCIAR_DIVIDAS: quer negociar ou parcelar dívidas existentes
- LIMPAR_NOME: quer limpar nome, remover restrições no Serasa/SPC
- OFF_TOPIC: se a mensagem for ofensiva, sem sentido, xingamentos ou totalmente fora do contexto financeiro de negócios (Ex: "qual a receita de bolo?", "troll").
- OUTRO: qualquer outro objetivo ou dúvida financeira geral.

{history_summary}

## MENSAGEM ATUAL DO LEAD
"{context.lead.message}"

Classifique o objetivo principal desta mensagem. Escolha apenas um goal da lista acima.
Considere o histórico: se o lead já demonstrou um goal antes, mantenha-o, A NÃO SER que o cliente claramente mude de ideia ou assunto na mensagem agora."""

        response = await self.llm.generate_structured(
            prompt=prompt,
            schema=GoalClassification,
            temperature=0.1,
        )

        goal = response.goal.upper().strip()

        if goal not in self.VALID_GOALS:
            self.logger.warning(
                "goal_classifier_invalid_llm_response",
                extra={
                    "trace_id": context.trace_id,
                    "raw_goal": goal,
                    "fallback": "OUTRO",
                },
            )
            return "OUTRO"

        return goal

    def _summarize_history(self, history: list[dict]) -> str:
        if not history:
            return ""
        recent = history[-4:]
        lines = ["## HISTÓRICO RECENTE"]
        for msg in recent:
            role = "Lead" if msg.get("role") == "user" else "Eleva"
            lines.append(f"{role}: {msg.get('content', '')}")
        return "\n".join(lines)