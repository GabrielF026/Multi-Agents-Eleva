import os
from typing import Dict, Any
from openai import AsyncOpenAI

from app.core.llm_provider import LLMProviderInterface


class OpenAIProvider(LLMProviderInterface):

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Dict[str, Any]:

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )

        return {
            "content": response.choices[0].message.content
        }