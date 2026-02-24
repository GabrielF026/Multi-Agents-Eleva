from abc import ABC, abstractmethod
from typing import Dict, Any


class LLMProviderInterface(ABC):
    """
    Interface base para qualquer provedor de LLM.
    Permite trocar OpenAI, Bedrock, Anthropic, etc
    sem alterar os agentes.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        Gera resposta baseada no prompt.
        """
        pass