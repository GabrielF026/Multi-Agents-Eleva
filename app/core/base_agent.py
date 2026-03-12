# app/core/base_agent.py

from abc import ABC, abstractmethod
from typing import Optional
import logging

from app.core.context import AgentContext


class BaseAgent(ABC):
    """
    Contrato base para todos os agentes do sistema Eleva.

    Todo agente deve:
    - Ter um nome único (usado pelo Orchestrator para logging e rastreamento)
    - Ter uma descrição clara do que faz (essencial para o roteamento na fase 2)
    - Implementar o método run(context) que recebe e retorna AgentContext
    - NUNCA lançar exceções não tratadas — erros devem ser registrados no context.errors

    Uso esperado:
        class MeuAgente(BaseAgent):
            async def run(self, context: AgentContext) -> AgentContext:
                # lógica do agente
                ...
    """

    def __init__(
        self,
        llm_provider,
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: str = "1.0.0",
    ):
        # Se o agente não passar um nome, usa o nome da própria classe
        self._name = name or self.__class__.__name__
        self._description = description or "Agente sem descrição definida."
        self._version = version
        self.llm = llm_provider
        self.logger = logging.getLogger(self._name)

    # ------------------------------------------------------------------
    # Propriedades de identidade do agente
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Nome único do agente. Usado no Orchestrator e nos logs."""
        return self._name

    @property
    def description(self) -> str:
        """
        Descrição do que esse agente faz.
        Na fase 2, o RouterAgent vai usar isso para decidir
        qual agente especialista acionar.
        """
        return self._description

    @property
    def version(self) -> str:
        """Versão do agente. Facilita rastrear qual versão processou um lead."""
        return self._version

    # ------------------------------------------------------------------
    # Contrato principal — único método obrigatório
    # ------------------------------------------------------------------

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentContext:
        """
        Executa a lógica do agente.

        Recebe o AgentContext com o estado atual do pipeline,
        executa sua responsabilidade específica,
        e retorna o contexto atualizado.

        REGRAS:
        - Nunca lançar exceção não tratada.
        - Em caso de erro, registrar em context.errors e retornar contexto seguro.
        - Nunca modificar context diretamente — usar context.model_copy(update={...})

        Args:
            context: Estado atual do pipeline de agentes.

        Returns:
            AgentContext atualizado com os resultados deste agente.
        """
        pass

    # ------------------------------------------------------------------
    # Métodos utilitários disponíveis para todos os agentes
    # ------------------------------------------------------------------

    def log_start(self, context: AgentContext) -> None:
        """Loga o início da execução do agente."""
        self.logger.info(
            f"[{self._name}] iniciando",
            extra={
                "trace_id": context.trace_id,
                "agent": self._name,
                "version": self._version,
            }
        )

    def log_success(self, context: AgentContext) -> None:
        """Loga a conclusão bem-sucedida do agente."""
        self.logger.info(
            f"[{self._name}] concluído com sucesso",
            extra={
                "trace_id": context.trace_id,
                "agent": self._name,
            }
        )

    def log_error(self, context: AgentContext, error: Exception) -> None:
        """Loga um erro ocorrido durante a execução do agente."""
        self.logger.error(
            f"[{self._name}] falhou: {str(error)}",
            extra={
                "trace_id": context.trace_id,
                "agent": self._name,
                "error": str(error),
            },
            exc_info=True
        )

    def register_error(self, context: AgentContext, error: Exception) -> AgentContext:
        """
        Registra o erro no contexto e retorna contexto seguro.
        Atalho para o padrão padrão de tratamento de falhas.
        """
        self.log_error(context, error)
        return context.model_copy(update={
            "errors": context.errors + [f"{self._name}: {str(error)}"]
        })

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self._name} version={self._version}>"