from typing import Dict, Any, List
from app.core.base_agent import BaseAgent
from app.core.llm_provider import LLMProviderInterface


class GoalClassifierAgent(BaseAgent):

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(name="GoalClassifierAgent")
        self.llm_provider = llm_provider

    async def classify(self, input_data: Dict[str, Any]) -> Dict[str, Any]:

        message = input_data.get("message", "").lower()
        history: List[Dict[str, str]] = input_data.get("history", [])

        # ======================================================
        # 🟢 1️⃣ Regras rápidas (baixo custo)
        # ======================================================
        if "financiamento" in message:
            return {"goal": "FINANCIAMENTO", "source": "rule"}

        if "crédito alto" in message or "credito alto" in message:
            return {"goal": "CREDITO_ALTO", "source": "rule"}

        if "alugar" in message or "aluguel" in message:
            return {"goal": "ALUGAR_IMOVEL", "source": "rule"}

        if "negociar dívida" in message or "negociar divida" in message:
            return {"goal": "NEGOCIAR_DIVIDAS", "source": "rule"}

        if (
            "limpar nome" in message
            or "serasa" in message
            or "nome sujo" in message
            or "nome negativado" in message
        ):
            return {"goal": "LIMPAR_NOME", "source": "rule"}

        # ======================================================
        # 🟡 2️⃣ Verificar histórico recente
        # ======================================================
        recent_text = ""

        if history:
            for msg in history[-5:]:
                if msg["role"] == "user":
                    recent_text += msg["content"].lower() + " "

        # Se já houve indicação clara anteriormente
        if "nome sujo" in recent_text or "limpar nome" in recent_text:
            return {"goal": "LIMPAR_NOME", "source": "history"}

        if "financiamento" in recent_text:
            return {"goal": "FINANCIAMENTO", "source": "history"}

        if "negociar dívida" in recent_text or "negociar divida" in recent_text:
            return {"goal": "NEGOCIAR_DIVIDAS", "source": "history"}

        # ======================================================
        # 🔵 3️⃣ Fallback LLM com contexto
        # ======================================================
        history_text = ""
        if history:
            for msg in history[-5:]:
                history_text += f'{msg["role"]}: {msg["content"]}\n'

        prompt = f"""
Analise a conversa abaixo e classifique o objetivo principal do cliente.

Categorias possíveis:
FINANCIAMENTO
CREDITO_ALTO
ALUGAR_IMOVEL
NEGOCIAR_DIVIDAS
LIMPAR_NOME
OUTRO

Conversa recente:
{history_text}

Mensagem atual:
{message}

Responda apenas com o nome exato da categoria.
Se houver contexto anterior forte, mantenha a categoria já indicada.
"""

        response = await self.llm_provider.generate(prompt)

        goal = response["content"].strip().upper()

        # Segurança extra
        allowed_goals = {
            "FINANCIAMENTO",
            "CREDITO_ALTO",
            "ALUGAR_IMOVEL",
            "NEGOCIAR_DIVIDAS",
            "LIMPAR_NOME",
            "OUTRO"
        }

        if goal not in allowed_goals:
            goal = "OUTRO"

        return {"goal": goal, "source": "llm"}

    async def respond(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": "GoalClassifier does not generate responses"}