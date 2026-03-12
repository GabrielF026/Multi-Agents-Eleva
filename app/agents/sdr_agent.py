# app/agents/sdr_agent.py

from app.core.base_agent import BaseAgent
from app.core.context import AgentContext
from app.core.llm_provider import LLMProviderInterface
from app.core.product_catalog import ProductCatalog, Product, PriceType


class SDRAgent(BaseAgent):
    """
    Agente SDR da Eleva.

    Responsabilidades:
    - Gerar resposta consultiva e humanizada
    - Adaptar tom à temperatura do lead (HOT/WARM/COLD)
    - Considerar TODO o histórico — inclusive o que o próprio SDR disse antes
    - Travar o produto recomendado durante toda a conversa
    - Variar o estilo de resposta — nunca começar sempre da mesma forma
    """

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(
            llm_provider=llm_provider,
            name="SDRAgent",
            description=(
                "Gera resposta humanizada considerando histórico completo, "
                "temperatura do lead e produto travado para a conversa."
            ),
            version="1.0.0",
        )

    async def run(self, context: AgentContext) -> AgentContext:
        self.log_start(context)

        try:
            # ----------------------------------------------------------
            # Produto travado: se já foi recomendado antes, reutiliza.
            # Evita que o produto mude no meio da conversa.
            # ----------------------------------------------------------
            if context.product_key:
                product = ProductCatalog.get_product(context.product_key)
                if not product:
                    product = ProductCatalog.get_product_by_goal(context.goal)
            else:
                product = ProductCatalog.get_product_by_goal(context.goal)

            messages = self._build_messages(context, product)

            llm_response = await self.llm.generate_with_history(
                messages=messages,
                temperature=0.7,   # levemente mais alto para variar o estilo
                max_tokens=600,
            )

            self.logger.info(
                "sdr_response_generated",
                extra={
                    "trace_id": context.trace_id,
                    "goal": context.goal,
                    "lead_score": context.lead_score,
                    "is_repeated": context.lead.is_repeated,
                    "has_history": bool(context.lead.history),
                    "history_length": len(context.lead.history),
                    "product": product.key,
                    "product_locked": bool(context.product_key),
                }
            )

            self.log_success(context)
            return context.model_copy(update={
                "sdr_response": llm_response.content,
                "product_key": product.key,
            })

        except Exception as e:
            updated = self.register_error(context, e)
            return updated.model_copy(update={
                "sdr_response": self._safe_fallback_response(context),
            })

    # ------------------------------------------------------------------
    # Construção das mensagens para o LLM
    # ------------------------------------------------------------------

    def _build_messages(self, context: AgentContext, product: Product) -> list[dict]:
        messages = []

        # System prompt — persona e regras fixas
        messages.append({
            "role": "system",
            "content": self._build_system_prompt(product),
        })

        # Histórico real da conversa (inclui o que o SDR disse antes)
        # Isso garante que o SDR se lembre das próprias respostas anteriores
        if context.lead.history:
            recent_history = context.lead.history[-12:]  # últimas 12 mensagens
            messages.extend(recent_history)

        # Prompt de instrução para a mensagem atual
        messages.append({
            "role": "user",
            "content": self._build_user_prompt(context, product),
        })

        return messages

    # ------------------------------------------------------------------
    # System prompt — persona fixa durante toda a conversa
    # ------------------------------------------------------------------

    def _build_system_prompt(self, product: Product) -> str:
        price_info = self._format_price_for_prompt(product)

        return f"""Você é o assistente virtual da Eleva, empresa especializada em soluções de crédito e recuperação financeira.

## QUEM VOCÊ É
Você é um consultor humano experiente, não um robô de atendimento.
Você fala de forma natural, direta e empática — como um amigo que entende do assunto.
Seu tom é de WhatsApp: informal, sem formalidade excessiva, sem jargões.

## SUA MISSÃO
Entender a dor real do cliente, conectar essa dor ao produto certo e preparar o lead para conversar com um especialista humano.
Você NÃO fecha vendas. Você qualifica e gera confiança.

## PRODUTO QUE VOCÊ REPRESENTA NESTA CONVERSA
Nome: {product.name}
O que resolve: {product.description}
Diferencial: {product.differentials}
Investimento: {price_info}

IMPORTANTE: Você representa APENAS este produto nesta conversa.
Não mude de produto, não mencione outros produtos da Eleva.

## ESTILO DE RESPOSTA — LEIA COM ATENÇÃO
- Máximo 4 linhas por resposta. Seja direto.
- NUNCA comece com "Entendo que", "Compreendo que", "Claro que" ou frases semelhantes.
- Varie SEMPRE o início das respostas. Exemplos de aberturas naturais:
  * "Boa, dá pra resolver isso sim."
  * "Faz sentido você querer resolver isso."
  * "Pelo que você contou, o caminho é..."
  * "Essa situação tem solução, e não é complicado."
  * "Dois anos é tempo demais nisso, vamos resolver."
  * "Ótima pergunta —"
  * "Na prática, o que acontece é..."
  * "Sem precisar de muito: o que a Eleva faz é..."
- NÃO repita a mesma abertura que você usou em mensagens anteriores nesta conversa.
- NÃO repita perguntas que o cliente já respondeu.
- NÃO use linguagem jurídica sem explicar.
- NÃO invente informações sobre o produto.
- NÃO prometa resultados garantidos.

## MEMÓRIA DA CONVERSA
Você tem acesso ao histórico completo desta conversa.
As mensagens com role "assistant" foram escritas por VOCÊ.
Mantenha total consistência com o que você já disse.
Se o cliente responder uma pergunta que você fez, reconheça a resposta antes de seguir."""

    # ------------------------------------------------------------------
    # User prompt — instrução específica para a mensagem atual
    # ------------------------------------------------------------------

    def _build_user_prompt(self, context: AgentContext, product: Product) -> str:
        temperature_guide = self._get_temperature_guide(context.lead_score)
        contact_context = self._get_contact_context(context)
        history_note = self._get_history_note(context)

        return f"""## SITUAÇÃO ATUAL DO ATENDIMENTO

{contact_context}
{history_note}

Objetivo do lead: {context.goal or "Não identificado"}
Temperatura atual: {context.lead_score or "WARM"}

## MENSAGEM ATUAL DO CLIENTE
"{context.lead.message}"

## COMO RESPONDER AGORA

{temperature_guide}

Escreva a resposta agora.
Tom: WhatsApp natural.
Limite: máximo 4 linhas.
Proibido: começar com "Entendo que" ou qualquer variação disso."""

    # ------------------------------------------------------------------
    # Nota sobre histórico para o user prompt
    # ------------------------------------------------------------------

    def _get_history_note(self, context: AgentContext) -> str:
        if not context.lead.history:
            return "Este é o primeiro contato do lead."

        turns = len([m for m in context.lead.history if m.get("role") == "user"])
        return (
            f"Esta é a mensagem {turns + 1} do lead nesta conversa. "
            f"Você já respondeu {turns} vez(es) antes. "
            "Considere o histórico acima ao formular sua resposta."
        )

    # ------------------------------------------------------------------
    # Guia de temperatura
    # ------------------------------------------------------------------

    def _get_temperature_guide(self, lead_score: str | None) -> str:
        guides = {
            "HOT": """LEAD QUENTE — Alta intenção, quer resolver agora.
- Seja direto e objetivo. Ele já está convencido, não precisa de convencimento.
- Dê um próximo passo claro e imediato.
- Conecte rapidamente com o especialista humano.
- Energia positiva, sem enrolação.
- NÃO faça perguntas desnecessárias — ele quer ação, não mais conversa.""",

            "WARM": """LEAD MORNO — Interesse real, mas ainda avaliando.
- Mostre que entende a situação dele sem exagerar na empatia.
- Explique brevemente como a Eleva resolve essa dor específica.
- Faça NO MÁXIMO uma pergunta estratégica — nunca mais de uma.
- Não pressione. Deixe ele sentir que está no controle.""",

            "COLD": """LEAD FRIO — Sem urgência agora.
- Seja leve, sem pressão alguma.
- Reconheça que talvez não seja o momento certo.
- Deixe uma porta aberta de forma genuína.
- NÃO tente vender. Plante uma semente de confiança.""",
        }
        return guides.get(lead_score or "WARM", guides["WARM"])

    # ------------------------------------------------------------------
    # Contexto de contato
    # ------------------------------------------------------------------

    def _get_contact_context(self, context: AgentContext) -> str:
        if context.lead.is_repeated:
            return (
                "TIPO: Retorno — este cliente já teve contato anterior com a Eleva.\n"
                "Reconheça que ele voltou de forma natural, sem soar como que você o esperava."
            )
        return "TIPO: Primeiro contato — construa confiança antes de qualquer coisa."

    # ------------------------------------------------------------------
    # Formatação do preço para o prompt
    # ------------------------------------------------------------------

    def _format_price_for_prompt(self, product: Product) -> str:
        price = product.price
        if price.type == PriceType.FIXED:
            return f"{price.display} — mencione apenas se o cliente perguntar."
        if price.type == PriceType.INSTALLMENT:
            parts = [price.display]
            if price.entry_value:
                parts.append(f"Entrada: {price.entry_value}")
            if price.installment_value and price.installment_count:
                parts.append(
                    f"{price.installment_count}x de {price.installment_value} após resultado"
                )
            return " | ".join(parts) + " — mencione apenas se o cliente perguntar."
        return (
            "Valor personalizado conforme análise. "
            "NÃO mencione valores — diga que um especialista fará a avaliação."
        )

    # ------------------------------------------------------------------
    # Fallback seguro
    # ------------------------------------------------------------------

    def _safe_fallback_response(self, context: AgentContext) -> str:
        self.logger.warning(
            "sdr_using_fallback_response",
            extra={"trace_id": context.trace_id}
        )
        return (
            "Oi! Recebi sua mensagem e já vou te conectar com um dos nossos especialistas. "
            "Em instantes alguém da nossa equipe entra em contato."
        )