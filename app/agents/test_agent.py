from typing import Dict, Any

from app.core.base_agent import BaseAgent
from app.core.llm_provider import LLMProviderInterface


class TestAgent(BaseAgent):

    def __init__(self, llm_provider: LLMProviderInterface):
        super().__init__(name="TestAgent")
        self.llm_provider = llm_provider

    async def classify(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"intent": "test"}

    async def respond(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
        Responda de forma profissional e amigável:
        {input_data.get("message")}
        """

        response = await self.llm_provider.generate(prompt)

        return {
            "agent": self.name,
            "response": response["content"]
        }