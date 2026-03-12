# app/core/product_catalog.py

import logging
from enum import Enum
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Enums — valores controlados
# ------------------------------------------------------------------

class GoalType(str, Enum):
    """
    Goals possíveis gerados pelo GoalClassifierAgent.
    Fonte única de verdade — usada pelo catálogo e pelo classificador.

    Fase 2: novos goals devem ser adicionados aqui primeiro,
    depois mapeados no GoalClassifierAgent e no ProductCatalog.
    """
    FINANCIAMENTO = "FINANCIAMENTO"
    CREDITO_ALTO = "CREDITO_ALTO"
    ALUGAR_IMOVEL = "ALUGAR_IMOVEL"
    NEGOCIAR_DIVIDAS = "NEGOCIAR_DIVIDAS"
    LIMPAR_NOME = "LIMPAR_NOME"
    OUTRO = "OUTRO"

    # Fase 2 — goals futuros (comentados até o classificador suportar)
    # NOME_LIMPO_SEM_CREDITO = "NOME_LIMPO_SEM_CREDITO"
    # RESTRICAO_BACEN = "RESTRICAO_BACEN"
    # PLANEJAMENTO_PATRIMONIAL = "PLANEJAMENTO_PATRIMONIAL"
    # CAPITAL_DE_GIRO = "CAPITAL_DE_GIRO"
    # INVESTIMENTO_ALTO = "INVESTIMENTO_ALTO"


class PriceType(str, Enum):
    """Como o preço do produto é estruturado."""
    FIXED = "FIXED"           # valor fixo (ex: R$ 99)
    INSTALLMENT = "INSTALLMENT"  # entrada + parcelas
    ON_DEMAND = "ON_DEMAND"   # sob análise/simulação


# ------------------------------------------------------------------
# Schema de produto — tipado e validado
# ------------------------------------------------------------------

class ProductPrice(BaseModel):
    """
    Estrutura de preço do produto.
    Separar o preço em campos permite ao SDRAgent
    apresentar o valor de forma consistente e contextual.
    """
    type: PriceType
    display: str  # texto para apresentar ao cliente
    entry_value: Optional[str] = None    # valor de entrada (se parcelado)
    installment_value: Optional[str] = None  # valor da parcela
    installment_count: Optional[int] = None  # número de parcelas


class Product(BaseModel):
    """
    Schema completo de um produto da Eleva.

    Todos os campos são obrigatórios para garantir que
    o SDRAgent sempre tenha o contexto necessário.

    Fase 2: adicionar campo `specialist_agent_class` para
    que o Orchestrator saiba qual agente especialista acionar.
    """
    key: str
    name: str
    price: ProductPrice
    description: str
    differentials: str
    indicated_for: list[GoalType]
    active: bool = True

    # Fase 2 — agente especialista por produto
    # specialist_agent: Optional[str] = None
    # ex: "FinanciamentoSpecialistAgent"


# ------------------------------------------------------------------
# Catálogo de produtos
# ------------------------------------------------------------------

class ProductCatalog:
    """
    Catálogo centralizado de produtos da Eleva.

    Fonte única de verdade para produtos, preços e mapeamento
    de goals para produtos recomendados.

    Regras:
    - Todo goal do GoalType deve estar mapeado em pelo menos um produto.
    - O produto fallback (RAIO_X_FINANCEIRO) deve estar sempre ativo.
    - Novos produtos da fase 2 entram com `active=False` até estarem prontos.

    Fase 2:
    - Adicionar campo `specialist_agent` em cada produto.
    - O Orchestrator usa esse campo para acionar o agente correto.
    """

    PRODUCTS: dict[str, Product] = {

        "RAIO_X_FINANCEIRO": Product(
            key="RAIO_X_FINANCEIRO",
            name="Raio-X Financeiro",
            price=ProductPrice(
                type=PriceType.FIXED,
                display="R$ 99",
            ),
            description=(
                "Diagnóstico técnico completo do perfil bancário do cliente. "
                "Identificamos como os bancos enxergam o perfil, "
                "quais travas de crédito estão ativas "
                "e o melhor caminho estratégico para desbloqueá-las."
            ),
            differentials=(
                "Análise feita por especialistas em crédito. "
                "Resultado em até 48 horas. "
                "Inclui plano de ação personalizado."
            ),
            indicated_for=[
                GoalType.FINANCIAMENTO,
                GoalType.CREDITO_ALTO,
                GoalType.OUTRO,
            ],
        ),

        "LIMPA_NOME": Product(
            key="LIMPA_NOME",
            name="Limpa Nome e Suspensão das Dívidas",
            price=ProductPrice(
                type=PriceType.INSTALLMENT,
                display="Entrada de R$ 197 + 6x de R$ 189 após nome limpo",
                entry_value="R$ 197",
                installment_value="R$ 189",
                installment_count=6,
            ),
            description=(
                "Suspensão da exposição das dívidas nos órgãos de proteção "
                "ao crédito como Serasa, SPC e Boa Vista, "
                "permitindo que o cliente volte a ter acesso ao crédito "
                "sem precisar negociar diretamente com os credores."
            ),
            differentials=(
                "Suspensão rápida das restrições. "
                "Você só paga as parcelas depois que o nome estiver limpo. "
                "Sem negociação direta com credores."
            ),
            indicated_for=[
                GoalType.NEGOCIAR_DIVIDAS,
                GoalType.ALUGAR_IMOVEL,
                GoalType.LIMPAR_NOME,
            ],
        ),

        "RATING_BANCARIO": Product(
            key="RATING_BANCARIO",
            name="Rating Bancário",
            price=ProductPrice(
                type=PriceType.FIXED,
                display="R$ 1.799 à vista ou R$ 1.980 parcelado",
            ),
            description=(
                "Reposicionamento estratégico do perfil financeiro "
                "no sistema bancário para aumentar as chances de aprovação "
                "de crédito mesmo após a limpeza do nome."
            ),
            differentials=(
                "Trabalha diretamente nos critérios de análise dos bancos. "
                "Resultado mensurável no score de crédito. "
                "Acompanhamento durante todo o processo."
            ),
            indicated_for=[],  # Fase 2: GoalType.NOME_LIMPO_SEM_CREDITO
            active=False,      # Inativo até o goal ser suportado
        ),

        "LIMPA_BACEN": Product(
            key="LIMPA_BACEN",
            name="Limpa Bacen",
            price=ProductPrice(
                type=PriceType.ON_DEMAND,
                display="Valor sob análise do caso",
            ),
            description=(
                "Reestruturação de registros junto ao Banco Central "
                "e regularização sistêmica financeira para clientes "
                "com restrições no sistema BACEN."
            ),
            differentials=(
                "Especialistas com experiência em regularização junto ao Banco Central. "
                "Análise do caso sem custo inicial. "
                "Processo totalmente conduzido pela equipe Eleva."
            ),
            indicated_for=[],  # Fase 2: GoalType.RESTRICAO_BACEN
            active=False,
        ),

        "CONSORCIO": Product(
            key="CONSORCIO",
            name="Consórcio",
            price=ProductPrice(
                type=PriceType.ON_DEMAND,
                display="Valor sob simulação personalizada",
            ),
            description=(
                "Estratégia de aquisição e alavancagem patrimonial "
                "para compra planejada de bens com custo menor "
                "que o financiamento tradicional."
            ),
            differentials=(
                "Sem juros — apenas taxa de administração. "
                "Possibilidade de lance para antecipar contemplação. "
                "Ideal para planejamento de médio e longo prazo."
            ),
            indicated_for=[],  # Fase 2: GoalType.PLANEJAMENTO_PATRIMONIAL
            active=False,
        ),

        "HOME_EQUITY": Product(
            key="HOME_EQUITY",
            name="Home Equity",
            price=ProductPrice(
                type=PriceType.ON_DEMAND,
                display="Valor sob análise do imóvel e perfil",
            ),
            description=(
                "Linha de crédito com garantia de imóvel para capital de giro, "
                "investimento ou reorganização financeira com taxas "
                "muito menores que crédito pessoal."
            ),
            differentials=(
                "Taxas a partir de 0,99% ao mês. "
                "Prazo de até 240 meses. "
                "Utiliza o imóvel como garantia sem perder a posse."
            ),
            indicated_for=[],  # Fase 2: GoalType.CAPITAL_DE_GIRO
            active=False,
        ),
    }

    # ------------------------------------------------------------------
    # Métodos públicos
    # ------------------------------------------------------------------

    @classmethod
    def get_product_by_goal(cls, goal: Optional[str]) -> Product:
        """
        Retorna o produto ativo mais indicado para o goal do cliente.

        Busca apenas em produtos ativos (active=True).
        Se nenhum produto ativo for encontrado para o goal,
        retorna o RAIO_X_FINANCEIRO como fallback diagnóstico.

        Args:
            goal: Goal identificado pelo GoalClassifierAgent.

        Returns:
            Product com todos os campos necessários para o SDRAgent.
        """
        if not goal:
            logger.warning(
                "product_catalog_no_goal_provided",
                extra={"fallback": "RAIO_X_FINANCEIRO"}
            )
            return cls._fallback_product()

        for product_key, product in cls.PRODUCTS.items():
            if not product.active:
                continue
            if goal in [g.value for g in product.indicated_for]:
                logger.info(
                    "product_catalog_match_found",
                    extra={
                        "goal": goal,
                        "product": product_key,
                    }
                )
                return product

        logger.warning(
            "product_catalog_no_match",
            extra={
                "goal": goal,
                "fallback": "RAIO_X_FINANCEIRO",
            }
        )
        return cls._fallback_product()

    @classmethod
    def get_product(cls, key: str) -> Optional[Product]:
        """
        Retorna um produto pelo key.

        Returns:
            Product se encontrado, None caso contrário.
            O chamador é responsável por tratar o None.
        """
        product = cls.PRODUCTS.get(key)

        if not product:
            logger.warning(
                "product_catalog_key_not_found",
                extra={"key": key}
            )

        return product

    @classmethod
    def get_active_products(cls) -> list[Product]:
        """
        Retorna lista de todos os produtos ativos.
        Útil para exibir catálogo completo na interface ou docs.
        """
        return [p for p in cls.PRODUCTS.values() if p.active]

    @classmethod
    def get_all_active_goals(cls) -> list[str]:
        """
        Retorna lista de todos os goals atendidos por produtos ativos.
        Útil para validar se o GoalClassifier está alinhado com o catálogo.
        """
        goals = set()
        for product in cls.PRODUCTS.values():
            if product.active:
                goals.update(g.value for g in product.indicated_for)
        return sorted(goals)

    # ------------------------------------------------------------------
    # Método interno
    # ------------------------------------------------------------------

    @classmethod
    def _fallback_product(cls) -> Product:
        """Retorna o produto diagnóstico padrão."""
        return cls.PRODUCTS["RAIO_X_FINANCEIRO"]