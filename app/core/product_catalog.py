from typing import Dict, List


class ProductCatalog:

    PRODUCTS: Dict[str, Dict] = {
        "RAIO_X_FINANCEIRO": {
            "name": "Raio-X Financeiro",
            "price": "R$ 99",
            "description": (
                "Diagnóstico técnico do perfil bancário do cliente. "
                "Identificamos como os bancos enxergam o perfil, "
                "quais travas de crédito estão ativas e o melhor caminho estratégico."
            ),
            "indicated_for": [
                "FINANCIAMENTO",
                "CREDITO_ALTO",
                "DUVIDA_GERAL"
            ]
        },

        "LIMPA_NOME": {
            "name": "Limpa Nome e Suspensão das Dívidas",
            "price": "Entrada R$ 197 + 6x de R$ 189 após nome limpo",
            "description": (
                "Suspensão da exposição das dívidas nos órgãos de proteção ao crédito "
                "como Serasa, SPC e Boa Vista, permitindo que o cliente volte a ter acesso ao crédito."
            ),
            "indicated_for": [
                "NEGOCIAR_DIVIDAS",
                "ALUGAR_IMOVEL",
                "LIMPAR_NOME"
            ]
        },

        "RATING_BANCARIO": {
            "name": "Rating Bancário",
            "price": "R$ 1.799 à vista ou R$ 1.980 parcelado",
            "description": (
                "Reposicionamento estratégico do perfil financeiro no sistema bancário "
                "para aumentar chances de aprovação de crédito."
            ),
            "indicated_for": [
                "NOME_LIMPO_SEM_CREDITO"
            ]
        },

        "LIMPA_BACEN": {
            "name": "Limpa Bacen",
            "price": "Sob análise",
            "description": (
                "Reestruturação de registros junto ao Banco Central e "
                "regularização sistêmica financeira."
            ),
            "indicated_for": [
                "RESTRICAO_BACEN"
            ]
        },

        "CONSORCIO": {
            "name": "Consórcio",
            "price": "Sob simulação",
            "description": (
                "Estratégia de aquisição e alavancagem patrimonial "
                "para compra planejada de bens."
            ),
            "indicated_for": [
                "PLANEJAMENTO_PATRIMONIAL"
            ]
        },

        "HOME_EQUITY": {
            "name": "Home Equity",
            "price": "Sob análise",
            "description": (
                "Linha de crédito com garantia de imóvel "
                "para capital de giro, investimento ou reorganização financeira."
            ),
            "indicated_for": [
                "CAPITAL_DE_GIRO",
                "INVESTIMENTO_ALTO"
            ]
        }
    }

    @classmethod
    def get_product_by_goal(cls, goal: str) -> Dict:
        """
        Retorna o produto mais indicado com base no objetivo do cliente.
        """
        for product_key, product_data in cls.PRODUCTS.items():
            if goal in product_data["indicated_for"]:
                return {
                    "key": product_key,
                    **product_data
                }

        # fallback padrão
        return {
            "key": "RAIO_X_FINANCEIRO",
            **cls.PRODUCTS["RAIO_X_FINANCEIRO"]
        }

    @classmethod
    def get_product(cls, key: str) -> Dict:
        return cls.PRODUCTS.get(key)