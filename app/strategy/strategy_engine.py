class StrategyEngine:

    @staticmethod
    def apply(lead_score: str, goal: str, sdr_result: dict):

        strategy = {
            "lead_score": lead_score,
            "next_action": None,
            "priority": None,
            "followup": None,
        }

        if lead_score == "HOT":
            strategy["next_action"] = "HANDOFF_TO_HUMAN"
            strategy["priority"] = "HIGH"

        elif lead_score == "WARM":
            strategy["next_action"] = "FOLLOWUP"
            strategy["priority"] = "MEDIUM"
            strategy["followup"] = {
                "enabled": True,
                "delay_days": 2
            }

        else:
            strategy["next_action"] = "NURTURE"
            strategy["priority"] = "LOW"
            strategy["followup"] = {
                "enabled": True,
                "delay_days": 5
            }

        return {
            "goal": goal,
            "recommended_product": sdr_result["recommended_product"],
            "product_name": sdr_result["product_name"],
            "response": sdr_result["response"],
            "strategy": strategy
        }