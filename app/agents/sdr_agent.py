from typing import Dict, Any, List
from app.core.base_agent import BaseAgent
from app.core.llm_provider import LLMProviderInterface
from app.core.product_catalog import ProductCatalog


class SDRAgent(BaseAgent):

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(name="SDRAgent")
        self.llm_provider = llm_provider

    async def classify(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": "SDRAgent does not classify"}

    async def respond(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": "Use handle() instead"}

    async def handle(
        self,
        message: str,
        goal: str,
        lead_score: str | None = None,
        history: List[Dict[str, str]] | None = None,
        is_repeated: bool = False
    ):

        product = ProductCatalog.get_product_by_goal(goal)

        if is_repeated:
            repetition_instruction = """
O cliente repetiu exatamente a mesma mensagem.

Explique novamente, mas:
- Não repita a mesma estrutura.
- Seja mais claro.
- Use palavras diferentes.
- Se possível, avance um passo na condução.
"""
        else:
            repetition_instruction = ""

        history_text = ""
        if history:
            for msg in history[-5:]:
                history_text += f'{msg["role"]}: {msg["content"]}\n'

        prompt = f"""
Você é um SDR consultivo da ElevaCredi.

HISTÓRICO RECENTE:
{history_text}

CONTEXTO:
Objetivo identificado: {goal}
Temperatura do lead: {lead_score}
Mensagem atual: "{message}"

Produto recomendado:
Nome: {product["name"]}
Preço: {product["price"]}
Descrição: {product["description"]}

{repetition_instruction}

REGRAS:
- Nunca mude o produto se o objetivo continuar o mesmo.
- Não repita exatamente a resposta anterior.
- Seja natural.
- Conduza para próximo passo humano quando fizer sentido.

Responda agora.
"""

        llm_response = await self.llm_provider.generate(prompt)

        return {
            "goal": goal,
            "recommended_product": product["key"],
            "product_name": product["name"],
            "response": llm_response["content"]
        }