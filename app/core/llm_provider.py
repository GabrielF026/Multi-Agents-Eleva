# app/core/llm_provider.py

from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Dict, Any
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMResponse:
    """Wrapper simples para a resposta do LLM."""
    def __init__(self, content: str):
        self.content = content


class LLMProviderInterface(ABC):
    """
    Interface base para provedores de LLM.

    Todo provider concreto deve implementar:
    - health_check: verifica disponibilidade
    - generate_structured: gera saída estruturada via Pydantic
    - generate_with_history: gera texto com histórico de conversa
    """

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o provider está disponível."""
        ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        temperature: float = 0.0,
        extra_messages: List[Dict[str, Any]] | None = None,
    ) -> T:
        """
        Gera uma resposta estruturada usando um schema Pydantic.
        Usado por GoalClassifierAgent e LeadScoreAgent.
        """
        ...

    @abstractmethod
    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 600,
    ) -> LLMResponse:
        """
        Gera texto considerando histórico completo de mensagens.
        Usado pelo SDRAgent.
        """
        ...