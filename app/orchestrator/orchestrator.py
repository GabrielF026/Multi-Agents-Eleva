from typing import Dict, Any, List, Optional

from app.infrastructure.openai_provider import OpenAIProvider
from app.agents.goalclassifier import GoalClassifierAgent
from app.agents.sdr_agent import SDRAgent
from app.agents.lead_score_agent import LeadScoreAgent
from app.strategy.strategy_engine import StrategyEngine


class Orchestrator:

    def __init__(self):
        self.llm_provider = OpenAIProvider()
        self.goalclassifier = GoalClassifierAgent(self.llm_provider)
        self.lead_score_agent = LeadScoreAgent(self.llm_provider)
        self.sdr_agent = SDRAgent(self.llm_provider)

    async def handle(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        current_goal: Optional[str] = None,
        is_repeated: bool = False
    ) -> Dict[str, Any]:

        classification = await self.goalclassifier.classify({
            "message": message,
            "history": history or []
        })

        new_goal = classification.get("goal", "OUTRO")

        if current_goal and new_goal == "OUTRO":
            goal = current_goal
        else:
            goal = new_goal

        lead_score_result = await self.lead_score_agent.score(
            message=message,
            sdr_response="",
            goal=goal
        )

        lead_score_value = lead_score_result.get("lead_score", "WARM")

        sdr_result = await self.sdr_agent.handle(
            message=message,
            goal=goal,
            lead_score=lead_score_value,
            history=history or [],
            is_repeated=is_repeated
        )

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