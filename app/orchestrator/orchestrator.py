from typing import Dict, Any

from app.infrastructure.openai_provider import OpenAIProvider
from app.agents.goalclassifier import GoalClassifierAgent
from app.agents.sdr_agent import SDRAgent
from app.agents.lead_score_agent import LeadScoreAgent
from app.strategy.strategy_engine import StrategyEngine


class Orchestrator:

    def __init__(self):
        # Provider principal de LLM
        self.llm_provider = OpenAIProvider()

        # Agentes do MVP
        self.goalclassifier = GoalClassifierAgent(self.llm_provider)
        self.lead_score_agent = LeadScoreAgent(self.llm_provider)
        self.sdr_agent = SDRAgent(self.llm_provider)

    async def handle(self, message: str) -> Dict[str, Any]:

        # 1️⃣ Classificar objetivo do cliente
        classification = await self.goalclassifier.classify({
            "message": message
        })

        goal = classification.get("goal", "OUTRO")

        # 2️⃣ Classificar temperatura do lead (antes do SDR)
        lead_score_result = await self.lead_score_agent.score(
            message=message,
            sdr_response="",   # ainda não temos resposta do SDR
            goal=goal
        )

        lead_score_value = lead_score_result.get("lead_score", "WARM")

        # 3️⃣ SDR gera abordagem estratégica já sabendo a temperatura
        sdr_result = await self.sdr_agent.handle(
            message=message,
            goal=goal,
            lead_score=lead_score_value
        )

        # 4️⃣ Aplicar estratégia final (handoff, prioridade, follow-up)
        final_result = StrategyEngine.apply(
            lead_score=lead_score_value,
            goal=goal,
            sdr_result=sdr_result
        )

        return {
            "classification": classification,
            "lead_score": lead_score_result,
            "final_response": final_result
        }