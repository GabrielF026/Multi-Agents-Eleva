# app/orchestrator/orchestrator.py

import logging
from typing import Optional

from app.core.context import AgentContext, LeadData
from app.core.base_agent import BaseAgent
from app.core.llm_provider import LLMProviderInterface
from app.strategy.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordenador central do pipeline de agentes da Eleva.

    Responsabilidades:
    - Criar o AgentContext com os dados da requisição
    - Executar os agentes em sequência (plug and play)
    - Aplicar a estratégia final via StrategyEngine
    - Retornar resultado consolidado estruturado
    - Registrar logs com trace_id em cada etapa

    O Orchestrator NÃO conhece a lógica interna de nenhum agente.
    Ele apenas coordena o fluxo e passa o contexto adiante.

    Adição de novo agente (fase 2):
        Basta adicionar na lista de agents no main.py.
        Nenhuma alteração necessária aqui.
    """

    def __init__(
        self,
        agents: list[BaseAgent],
        llm_provider: LLMProviderInterface,
    ):
        """
        Args:
            agents: Lista ordenada de agentes a executar no pipeline.
                    A ordem da lista define a ordem de execução.
            llm_provider: Provider de LLM para health check e uso futuro.
        """
        self._agents = agents
        self._llm_provider = llm_provider

        logger.info(
            "orchestrator_initialized",
            extra={
                "agents": [a.name for a in self._agents],
                "agent_count": len(self._agents),
            }
        )

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    async def handle(
        self,
        message: str,
        history: Optional[list[dict]] = None,
        current_goal: Optional[str] = None,
        is_repeated: bool = False,
    ) -> dict:
        """
        Executa o pipeline completo para uma mensagem recebida.

        Fluxo:
            1. Cria AgentContext com os dados da requisição
            2. Executa cada agente em sequência
            3. Aplica StrategyEngine ao contexto final
            4. Retorna resultado consolidado

        Args:
            message: Mensagem atual do cliente.
            history: Histórico de mensagens anteriores da conversa.
            current_goal: Goal identificado em interações anteriores.
            is_repeated: True se o cliente já teve contato anterior.

        Returns:
            Dicionário com classificação, score, resposta SDR e estratégia.
        """

        # Cria contexto inicial da requisição
        context = AgentContext(
            lead=LeadData(
                message=message,
                history=history or [],
                current_goal=current_goal,
                is_repeated=is_repeated,
            )
        )

        logger.info(
            "orchestration_started",
            extra={
                "trace_id": context.trace_id,
                "message_preview": message[:80],
                "has_history": bool(history),
                "is_repeated": is_repeated,
                "current_goal": current_goal,
            }
        )

        # Verifica disponibilidade do LLM antes de iniciar
        # Evita executar o pipeline inteiro para falhar no primeiro agente
        llm_available = await self._llm_provider.health_check()
        if not llm_available:
            logger.critical(
                "orchestration_aborted_llm_unavailable",
                extra={"trace_id": context.trace_id}
            )
            return self._unavailable_response(context)

        # Executa agentes em sequência
        context = await self._run_pipeline(context)

        # Aplica estratégia operacional ao contexto final
        context = self._apply_strategy(context)

        logger.info(
            "orchestration_completed",
            extra={
                "trace_id": context.trace_id,
                "goal": context.goal,
                "lead_score": context.lead_score,
                "errors": context.errors,
                "has_errors": bool(context.errors),
            }
        )

        return self._build_response(context)

    async def health_check(self) -> dict:
        """
        Verifica saúde do Orchestrator e do LLM provider.
        Usado pelo endpoint /health da API.
        """
        llm_ok = await self._llm_provider.health_check()
        return {
            "status": "ok" if llm_ok else "degraded",
            "llm_available": llm_ok,
            "agents_registered": [a.name for a in self._agents],
            "agent_count": len(self._agents),
        }

    # ------------------------------------------------------------------
    # Execução do pipeline
    # ------------------------------------------------------------------

    async def _run_pipeline(self, context: AgentContext) -> AgentContext:
        """
        Executa todos os agentes em sequência.

        Cada agente recebe o contexto atual e retorna o contexto atualizado.
        Se um agente falhar de forma inesperada (não tratada internamente),
        o erro é registrado e o pipeline continua com o contexto anterior.

        Agentes bem implementados NUNCA lançam exceção — tratam internamente
        e registram em context.errors. Esta camada é o último recurso.
        """
        for agent in self._agents:
            logger.info(
                "agent_starting",
                extra={
                    "trace_id": context.trace_id,
                    "agent": agent.name,
                    "agent_version": agent.version,
                }
            )

            try:
                context = await agent.run(context)

                logger.info(
                    "agent_completed",
                    extra={
                        "trace_id": context.trace_id,
                        "agent": agent.name,
                        "errors_so_far": len(context.errors),
                    }
                )

            except Exception as e:
                # Falha crítica não tratada dentro do agente
                # Registra e continua — pipeline não para por um agente
                logger.critical(
                    "agent_unhandled_failure",
                    extra={
                        "trace_id": context.trace_id,
                        "agent": agent.name,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                context = context.model_copy(update={
                    "errors": context.errors + [
                        f"{agent.name}: falha crítica não tratada — {str(e)}"
                    ]
                })

            # Verifica o short-circuit (Bypass imposto por algum Agente Seguro)
            if getattr(context, "fast_forward_response", None):
                logger.info("orchestrator_fast_forward_triggered", extra={"trace_id": context.trace_id, "agent": agent.name})
                context = context.model_copy(update={
                    "sdr_response": context.fast_forward_response
                })
                break
                
        return context

    # ------------------------------------------------------------------
    # Estratégia final
    # ------------------------------------------------------------------

    def _apply_strategy(self, context: AgentContext) -> AgentContext:
        """
        Aplica o StrategyEngine ao contexto final do pipeline.
        Registra erro sem interromper caso o engine falhe.
        """
        try:
            strategy = StrategyEngine.apply(
                lead_score=context.lead_score,
                goal=context.goal,
                sdr_result=context.sdr_response,
            )
            strategy_with_trace = strategy.model_copy(
                update={"trace_id": context.trace_id}
            )
            return context.model_copy(update={
                "strategy": strategy_with_trace.model_dump()
            })

        except Exception as e:
            logger.error(
                "strategy_engine_failed",
                extra={
                    "trace_id": context.trace_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return context.model_copy(update={
                "errors": context.errors + [f"strategy_engine: {str(e)}"]
            })

    # ------------------------------------------------------------------
    # Construção da resposta final
    # ------------------------------------------------------------------

    def _build_response(self, context: AgentContext) -> dict:
        """
        Constrói a resposta final estruturada a partir do AgentContext.

        Formato estável — mudanças internas no AgentContext
        não afetam o contrato da API enquanto este método
        for mantido consistente.
        """
        return {
            "trace_id": context.trace_id,
            "classification": {
                "goal": context.goal,
                "source": context.goal_source,
            },
            "lead_score": {
                "score": context.lead_score,
                "source": context.lead_score_source,
            },
            "sdr_response": context.sdr_response,
            "strategy": context.strategy,
            "pipeline_errors": context.errors,
            "has_errors": bool(context.errors),
        }

    def _unavailable_response(self, context: AgentContext) -> dict:
        """
        Resposta segura quando o LLM está indisponível.
        Mantém o contrato de resposta da API.
        """
        return {
            "trace_id": context.trace_id,
            "classification": {"goal": None, "source": None},
            "lead_score": {"score": None, "source": None},
            "sdr_response": (
                "Estamos com uma instabilidade momentânea. "
                "Nossa equipe já foi notificada e entrará em contato em breve."
            ),
            "strategy": None,
            "pipeline_errors": ["llm_provider: serviço indisponível"],
            "has_errors": True,
        }
