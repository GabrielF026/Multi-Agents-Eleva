from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.orchestrator import Orchestrator
from app.infrastructure.database import init_db, get_db

from app.services.lead_repository import LeadRepository
from app.services.conversation_repository import ConversationRepository
from app.services.message_repository import MessageRepository
from app.services.classification_repository import ClassificationRepository
from app.services.action_repository import ActionRepository

from app.models.enums import (
    MessageSender,
    ClassificationSource,
    LeadScore,
    Goal,
    Priority,
    LeadStatus,
)

app = FastAPI(title="Multi Agents Eleva")
orchestrator = Orchestrator()


@app.on_event("startup")
async def startup_event():
    await init_db()


class MessageRequest(BaseModel):
    email: str
    name: str | None = None
    phone: str | None = None
    message: str


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/chat")
async def chat(
    request: MessageRequest,
    db: AsyncSession = Depends(get_db)
):
    lead_repo = LeadRepository(db)
    conversation_repo = ConversationRepository(db)
    message_repo = MessageRepository(db)
    classification_repo = ClassificationRepository(db)
    action_repo = ActionRepository(db)

    # =========================
    # 1️⃣ Lead
    # =========================
    lead = await lead_repo.get_by_email(request.email)

    if not lead:
        lead = await lead_repo.create(
            email=request.email,
            name=request.name,
            phone=request.phone,
        )

    # =========================
    # 2️⃣ Conversation
    # =========================
    conversation = await conversation_repo.get_latest_by_lead(lead.id)

    if not conversation:
        conversation = await conversation_repo.create(lead.id)

    # =========================
    # 3️⃣ Detectar repetição
    # =========================
    last_message = await message_repo.get_last_message_by_conversation(
        conversation.id
    )

    is_repeated = False

    if (
        last_message
        and last_message.sender.name == "CLIENT"
        and last_message.content.strip().lower() == request.message.strip().lower()
    ):
        is_repeated = True

    # =========================
    # 4️⃣ Histórico
    # =========================
    history_messages = await message_repo.get_last_messages_by_conversation(
        conversation.id,
        limit=10
    )

    formatted_history = []
    for msg in history_messages:
        role = "assistant" if msg.sender.name == "SYSTEM" else "user"
        formatted_history.append({
            "role": role,
            "content": msg.content
        })

    # =========================
    # 5️⃣ Salvar mensagem cliente
    # =========================
    await message_repo.create(
        conversation_id=conversation.id,
        sender=MessageSender.CLIENT,
        content=request.message
    )

    if lead.status == LeadStatus.NEW:
        lead.update_status(LeadStatus.CONTACTED)
        await lead_repo.save(lead)

    # =========================
    # 6️⃣ Orchestrator
    # =========================
    result = await orchestrator.handle(
        message=request.message,
        history=formatted_history,
        current_goal=lead.goal.name if lead.goal else None,
        is_repeated=is_repeated
    )

    classification_data = result.get("classification")
    lead_score_data = result.get("lead_score")
    strategy_data = result.get("final_response", {}).get("strategy")

    # =========================
    # 🔒 Proteger goal
    # =========================
    if classification_data:
        new_goal = classification_data["goal"]

        if lead.goal and new_goal == "OUTRO":
            classification_data["goal"] = lead.goal.name

        await classification_repo.create(
            lead_id=lead.id,
            goal=Goal[classification_data["goal"]],
            source=ClassificationSource[classification_data["source"].upper()]
        )

    # =========================
    # 7️⃣ Salvar resposta SYSTEM
    # =========================
    final_response = result.get("final_response")

    if final_response and final_response.get("response"):
        await message_repo.create(
            conversation_id=conversation.id,
            sender=MessageSender.SYSTEM,
            content=final_response["response"]
        )

    # =========================
    # 8️⃣ Salvar Action
    # =========================
    if strategy_data:
        followup = strategy_data.get("followup")

        await action_repo.create(
            lead_id=lead.id,
            next_action=strategy_data["next_action"],
            priority=Priority[strategy_data["priority"]],
            followup_enabled=followup["enabled"] if followup else False,
            followup_delay_days=followup["delay_days"] if followup else None,
        )

    # =========================
    # 9️⃣ Atualizar Lead
    # =========================
    if strategy_data and lead_score_data and classification_data:

        effective_goal = (
            lead.goal if lead.goal
            else Goal[classification_data["goal"]]
        )

        lead.apply_strategy(
            lead_score=LeadScore[lead_score_data["lead_score"]],
            goal=effective_goal,
            priority=Priority[strategy_data["priority"]],
            next_action=strategy_data["next_action"],
        )

        await lead_repo.save(lead)

    return result