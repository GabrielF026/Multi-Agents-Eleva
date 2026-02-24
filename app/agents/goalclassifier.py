from typing import Dict, Any
from app.core.base_agent import BaseAgent
from app.core.llm_provider import LLMProviderInterface


class GoalClassifierAgent(BaseAgent):

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(name="GoalClassifierAgent")
        self.llm_provider = llm_provider

    async def classify(self, input_data: Dict[str, Any]) -> Dict[str, Any]:

        message = input_data.get("message", "").lower()

        # 🟢 Regras rápidas (baixo custo)
        if "financiamento" in message:
            return {"goal": "FINANCIAMENTO", "source": "rule"}

        if "crédito alto" in message or "credito alto" in message:
            return {"goal": "CREDITO_ALTO", "source": "rule"}

        if "alugar" in message or "aluguel" in message:
            return {"goal": "ALUGAR_IMOVEL", "source": "rule"}

        if "negociar dívida" in message or "negociar divida" in message:
            return {"goal": "NEGOCIAR_DIVIDAS", "source": "rule"}

        if "limpar nome" in message or "serasa" in message:
            return {"goal": "LIMPAR_NOME", "source": "rule"}

        # 🔵 Fallback LLM
        prompt = f"""
Classifique o objetivo do cliente em uma das categorias abaixo:

FINANCIAMENTO
CREDITO_ALTO
ALUGAR_IMOVEL
NEGOCIAR_DIVIDAS
LIMPAR_NOME
OUTRO

Mensagem:
{message}

Responda apenas com o nome da categoria.
"""

        response = await self.llm_provider.generate(prompt)

        goal = response["content"].strip().upper()

        return {"goal": goal, "source": "llm"}

    # 🔴 Método obrigatório por herdar de BaseAgent
    async def respond(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        GoalClassifier não responde diretamente ao cliente.
        Implementado apenas para satisfazer a classe abstrata BaseAgent.
        """
        return {"message": "GoalClassifier does not generate responses"}