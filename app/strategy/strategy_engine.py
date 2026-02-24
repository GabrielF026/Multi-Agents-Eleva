from typing import Dict, Any


class StrategyEngine:

    @staticmethod
    def apply(
        lead_score: str,
        goal: str,
        sdr_result: Dict[str, Any]
    ) -> Dict[str, Any]:

        response_text = sdr_result["response"]

        # 🔥 HOT → humano imediato
        if lead_score == "HOT":

            response_text += (
                "\n\nVou encaminhar seu atendimento com prioridade para um especialista humano "
                "que vai dar continuidade agora."
            )

            next_action = "HANDOFF_TO_HUMAN"
            priority = "HIGH"
            followup = None

        # 🌡️ WARM → humano também (mas média prioridade)
        elif lead_score == "WARM":

            response_text += (
                "\n\nVou direcionar seu caso para um especialista humano que pode te explicar "
                "com mais detalhes e tirar todas as suas dúvidas."
            )

            next_action = "HANDOFF_TO_HUMAN"
            priority = "MEDIUM"
            followup = {
                "enabled": True,
                "delay_days": 2
            }

        # ❄️ COLD → nutrição automática
        elif lead_score == "COLD":

            response_text = (
                "Entendo que talvez esse não seja o momento ideal.\n\n"
                "Se fizer sentido mais pra frente, posso te ajudar a entender melhor "
                "qual seria o melhor momento para resolver isso."
            )

            next_action = "NURTURE"
            priority = "LOW"
            followup = {
                "enabled": True,
                "delay_days": 4
            }

        else:
            next_action = "NONE"
            priority = "LOW"
            followup = None

        sdr_result["response"] = response_text
        sdr_result["strategy"] = {
            "lead_score": lead_score,
            "next_action": next_action,
            "priority": priority,
            "followup": followup
        }

        return sdr_result