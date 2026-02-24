from typing import Dict, Any
from app.core.base_agent import BaseAgent
from app.core.llm_provider import LLMProviderInterface


class LeadScoreAgent(BaseAgent):

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(name="LeadScoreAgent")
        self.llm_provider = llm_provider

    # obrigatório por causa do BaseAgent
    async def classify(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": "LeadScoreAgent does not classify"}

    # obrigatório por causa do BaseAgent
    async def respond(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": "Use score() instead"}

    # 🔥 método real
    async def score(
        self,
        message: str,
        sdr_response: str,
        goal: str | None = None
    ) -> Dict[str, Any]:

        message_lower = message.lower()

        # =========================
        # 🔥 REGRAS HOT (alta intenção)
        # =========================

        hot_keywords = [
            "quero fechar",
            "quero contratar",
            "como contrato",
            "como fechar",
            "qual o valor",
            "qual o preço",
            "me manda o link",
            "vamos começar",
            "preciso resolver hoje",
            "urgente",
            "posso pagar"
        ]

        if any(k in message_lower for k in hot_keywords):
            return {"lead_score": "HOT", "source": "rule_hot"}

        # Se objetivo claro + urgência → HOT
        if goal in ["LIMPAR_NOME", "FINANCIAMENTO"] and "urgente" in message_lower:
            return {"lead_score": "HOT", "source": "rule_goal_urgency"}

        # =========================
        # ❄️ REGRAS COLD (baixa intenção)
        # =========================

        cold_keywords = [
            "vou pensar",
            "depois eu vejo",
            "muito caro",
            "não tenho interesse",
            "não agora",
            "só estava vendo",
            "não quero",
            "talvez depois"
        ]

        if any(k in message_lower for k in cold_keywords):
            return {"lead_score": "COLD", "source": "rule_cold"}

        # =========================
        # 🌡️ REGRAS WARM (dor declarada)
        # =========================

        warm_indicators = [
            "estou com problema",
            "não estou conseguindo",
            "meu nome está",
            "banco recusou",
            "preciso entender",
            "não sei o que fazer"
        ]

        if any(k in message_lower for k in warm_indicators):
            return {"lead_score": "WARM", "source": "rule_warm"}

        # =========================
        # 🤖 FALLBACK LLM
        # =========================

        prompt = f"""
Você é um classificador de leads comerciais.

Classifique o lead como:

HOT  → pronto para comprar
WARM → interessado mas com dúvidas
COLD → desinteressado ou não pronto

Contexto:
Objetivo identificado: {goal}

Mensagem do cliente:
{message}

Resposta do SDR:
{sdr_response}

Regras:
- Responda apenas com HOT, WARM ou COLD.
- Não explique.
"""

        response = await self.llm_provider.generate(prompt)

        score = response["content"].strip().upper()

        # Segurança contra resposta inválida
        if score not in ["HOT", "WARM", "COLD"]:
            score = "WARM"

        return {"lead_score": score, "source": "llm"}