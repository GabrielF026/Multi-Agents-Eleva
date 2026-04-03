# app/agents/lead_score_agent.py

import logging
from typing import Optional
from pydantic import BaseModel

from app.core.base_agent import BaseAgent
from app.core.context import AgentContext
from app.core.llm_provider import LLMProviderInterface

logger = logging.getLogger(__name__)


class LeadScoreOutput(BaseModel):
    score: str        # HOT, WARM ou COLD
    reasoning: str    # Justificativa
    confidence: str   # high, medium ou low


class LeadScoreAgent(BaseAgent):
    """
    Classifica a temperatura do lead: HOT, WARM ou COLD.

    Regras de negócio:
    - Se já foi HOT (na mensagem anterior ou no contexto), continua HOT.
    - Nunca rebaixa score — só mantém ou sobe.
    - Para goal LIMPAR_NOME com histórico HOT, ignorar downgrades do LLM.
    """

    _HOT_KEYWORDS: list[str] = [
        "quanto custa", "quanto fica", "quero contratar", "quero começar",
        "como contrato", "me passa o contato", "quero resolver hoje",
        "preciso resolver hoje", "preciso urgente", "urgente", "quanto é",
        "me manda o link", "vou fechar", "pode me ligar", "me liga",
        "quero falar com alguém", "quero o especialista", "tô pronto",
        "to pronto", "bora", "fechado", "combinado", "pode mandar",
        "manda o contrato", "quero resolver", "preciso resolver",
        "quero limpar", "preciso limpar", "como faço para contratar",
    ]

    _COLD_KEYWORDS: list[str] = [
        "só curiosidade", "so curiosidade", "só estou vendo",
        "so estou vendo", "vou pensar", "depois eu vejo",
        "não tenho pressa", "nao tenho pressa", "talvez", "quem sabe",
        "futuramente", "não sei ainda", "nao sei ainda",
        "só quero saber o preço", "sem compromisso",
        "por enquanto não", "por enquanto nao",
    ]

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(
            llm_provider=llm_provider,
            name="LeadScoreAgent",
            description=(
                "Classifica a temperatura do lead. "
                "Preserva HOT e só permite upgrades."
            ),
            version="1.0.0",
        )

    async def run(self, context: AgentContext) -> AgentContext:
        self.log_start(context)

        # 1) Score anterior (do payload ou do próprio contexto)
        previous_score = context.lead.current_lead_score or context.lead_score

        # -------------------------------------------------------------------
        # SHORT-CIRCUIT: Bypass Atendimento Humano
        # -------------------------------------------------------------------
        msg_lower = context.lead.message.lower()
        if any(term in msg_lower for term in ["falar com atendente", "humano", "pessoa real", "passa para alguem", "atendimento humano", "pessoa", "atendimento normal"]):
            logger.info("lead_score_bypass_human_handoff", extra={"trace_id": context.trace_id})
            self.log_success(context)
            return context.model_copy(update={
                "lead_score": "HOT",
                "lead_score_source": "rule_human_handoff",
                "fast_forward_response": "Perfeito! Estou te transferindo agora mesmo para um especialista humano da Eleva. Aguarde um instante na linha."
            })

        # 2) Regra absoluta: se já era HOT, continua HOT (não chama LLM)
        if previous_score == "HOT":
            logger.info(
                "lead_score_preserved_hot",
                extra={
                    "trace_id": context.trace_id,
                    "previous_score": previous_score,
                    "goal": context.goal,
                },
            )
            self.log_success(context)
            return context.model_copy(update={
                "lead_score": "HOT",
                "lead_score_source": "preserved",
            })

        try:
            # 3) Regras por keywords (mais baratas que LLM)
            rule_score = self._classify_by_rules(context.lead.message)

            if rule_score:
                final_score = self._resolve_score(previous_score, rule_score)
                logger.info(
                    "lead_score_classified_by_rule",
                    extra={
                        "trace_id": context.trace_id,
                        "score": final_score,
                        "rule_score": rule_score,
                        "previous_score": previous_score,
                    },
                )
                self.log_success(context)
                return context.model_copy(update={
                    "lead_score": final_score,
                    "lead_score_source": f"rule_{final_score.lower()}",
                })

            # 4) Fallback LLM (quando as regras não são conclusivas)
            llm_score = await self._classify_by_llm(context)

            # Trava extra: para LIMPAR_NOME com histórico HOT,
            # não deixa o LLM rebaixar.
            if (
                context.goal == "LIMPAR_NOME"
                and context.lead.current_lead_score == "HOT"
                and llm_score in {"WARM", "COLD"}
            ):
                logger.info(
                    "lead_score_llm_downgrade_ignored_for_limpar_nome",
                    extra={
                        "trace_id": context.trace_id,
                        "llm_score": llm_score,
                        "previous_score": "HOT",
                    },
                )
                final_score = "HOT"
            else:
                final_score = self._resolve_score(previous_score, llm_score)

            logger.info(
                "lead_score_classified_by_llm",
                extra={
                    "trace_id": context.trace_id,
                    "score": final_score,
                    "llm_score": llm_score,
                    "previous_score": previous_score,
                },
            )
            self.log_success(context)
            return context.model_copy(update={
                "lead_score": final_score,
                "lead_score_source": "llm",
            })

        except Exception as e:
            updated = self.register_error(context, e)
            logger.error(
                "lead_score_agent_error",
                extra={
                    "trace_id": context.trace_id,
                    "error": str(e),
                },
            )
            return updated.model_copy(update={
                "lead_score": previous_score or "WARM",
                "lead_score_source": "fallback_error",
            })

    @staticmethod
    def _resolve_score(current: Optional[str], new: str) -> str:
        """
        Nunca rebaixa score: só mantém ou sobe.
        Hierarquia: HOT > WARM > COLD.
        """
        hierarchy = {"COLD": 0, "WARM": 1, "HOT": 2}
        current_level = hierarchy.get(current or "COLD", 0)
        new_level = hierarchy.get(new, 1)

        if new_level >= current_level:
            return new
        return current or "WARM"

    def _classify_by_rules(self, message: str) -> Optional[str]:
        msg_lower = message.lower()
        for keyword in self._HOT_KEYWORDS:
            if keyword in msg_lower:
                return "HOT"
        for keyword in self._COLD_KEYWORDS:
            if keyword in msg_lower:
                return "COLD"
        return None

    async def _classify_by_llm(self, context: AgentContext) -> str:
        history_text = self._summarize_history(context.lead.history)

        prompt = f"""Você é um especialista em qualificação de leads da Eleva,
empresa brasileira focada em soluções de crédito e recuperação financeira.

Sua tarefa é classificar a temperatura do lead com base na conversa.

## DEFINIÇÕES DE TEMPERATURA

HOT:
- Urgência clara ou intenção imediata de resolver o problema
- Pergunta sobre preço, como contratar, próximos passos
- Usa termos como "hoje", "agora", "urgente", "quanto custa", "quero contratar"
- Pede para falar com um especialista humano
- Qualquer sinal forte de que quer avançar AGORA

WARM:
- Dor/problema real, mas sem decisão imediata
- Está pesquisando, querendo entender como funciona
- Interesse genuíno, mas sem pressa explícita
- Pergunta "como funciona?", "qual a solução?", "nunca tentei antes"

COLD:
- Sem urgência, mais curiosidade
- Linguagem vaga, sem dor específica
- Diz coisas como "vou pensar", "talvez", "mais pra frente"
- Não demonstra vontade real de avançar

{history_text}

## MENSAGEM ATUAL DO LEAD
"{context.lead.message}"

## CONTEXTO ADICIONAL
- Objetivo identificado: {context.goal or "não identificado"}
- Temperatura anterior (se houver): {context.lead.current_lead_score or context.lead_score or "ainda não classificado"}

## REGRA DE NEGÓCIO IMPORTANTE
Se o lead já demonstrou comportamento HOT no passado, 
você deve manter HOT, a menos que ele deixe CLARO que não quer mais seguir.
Exemplo de frases que indicam esfriamento: "não quero mais", "desisti", "não tenho interesse".

## SAÍDA OBRIGATÓRIA (JSON)
Responda APENAS com um objeto JSON contendo exatamente estes três campos:
{{
  "score": "HOT" ou "WARM" ou "COLD",
  "reasoning": "explicação breve em português",
  "confidence": "high" ou "medium" ou "low"
}}"""

        response = await self.llm.generate_structured(
            prompt=prompt,
            schema=LeadScoreOutput,
            temperature=0.1,
        )

        score = response.score.upper().strip()

        if score not in {"HOT", "WARM", "COLD"}:
            logger.warning(
                "lead_score_invalid_llm_response",
                extra={
                    "trace_id": context.trace_id,
                    "raw_score": score,
                    "fallback": "WARM",
                },
            )
            return "WARM"

        return score

    def _summarize_history(self, history: list[dict]) -> str:
        if not history:
            return ""
        recent = history[-6:]
        lines = ["## HISTÓRICO RECENTE DA CONVERSA"]
        for msg in recent:
            role = "Lead" if msg.get("role") == "user" else "Eleva"
            lines.append(f"{role}: {msg.get('content', '')}")
        return "\n".join(lines)