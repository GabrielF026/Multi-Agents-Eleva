from typing import Dict, Any
from app.core.base_agent import BaseAgent
from app.core.llm_provider import LLMProviderInterface
from app.core.product_catalog import ProductCatalog


class SDRAgent(BaseAgent):

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(name="SDRAgent")
        self.llm_provider = llm_provider

    # ✅ obrigatório por causa do BaseAgent
    async def classify(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": "SDRAgent does not classify"}

    # ✅ obrigatório por causa do BaseAgent
    async def respond(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"message": "Use handle() instead"}

    # 🔵 método real usado no fluxo
    async def handle(self, message: str, goal: str, lead_score: str | None = None):

        product = ProductCatalog.get_product_by_goal(goal)

        prompt = f"""
Você é um SDR consultivo da ElevaCredi especializado em qualificação estratégica de leads.

CONTEXTO:
Objetivo identificado: {goal}
Temperatura do lead: {lead_score}
Mensagem do cliente: "{message}"

Produto recomendado:
Nome: {product["name"]}
Preço: {product["price"]}
Descrição resumida: {product["description"]}

REGRAS ABSOLUTAS:
- Não invente objeções que o cliente não mencionou.
- Não assuma problemas que não foram ditos.
- Não escreva textos longos demais.
- Use linguagem natural, como conversa de WhatsApp.
- Seja claro e direto.
- Demonstre entendimento real da dor.
- Não pareça robô.
- Sempre conduza para o próximo passo humano.

COMPORTAMENTO POR TEMPERATURA:

Se HOT:
- Seja direto.
- Confirme intenção.
- Prepare para encaminhamento humano.
- Use energia segura e objetiva.

Se WARM:
- Demonstre empatia.
- Explique brevemente o porquê da solução.
- Faça 1 pergunta estratégica que ajude o humano depois.

Se COLD:
- Seja leve.
- Não pressione.
- Ofereça ajuda futura.
- Não tente vender.

ESTRUTURA IDEAL:
1. Reconhecer dor real.
2. Conectar com solução.
3. Conduzir próximo passo.

Responda agora.
"""

        llm_response = await self.llm_provider.generate(prompt)

        return {
            "goal": goal,
            "recommended_product": product["key"],
            "product_name": product["name"],
            "response": llm_response["content"]
        }