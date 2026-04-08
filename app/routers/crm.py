from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.models.database_models import Interaction, Lead, LeadStatus
from app.orchestrator.orchestrator import Orchestrator


router = APIRouter(prefix="/crm", tags=["CRM"])


CRM_STAGES = [
    {
        "id": LeadStatus.NEW.value,
        "name": "Novos leads",
        "description": "Leads recebidos e ainda sem qualificacao operacional.",
        "order": 1,
    },
    {
        "id": LeadStatus.MARKETING_NURTURE.value,
        "name": "Nutricao",
        "description": "Leads COLD em fluxo de conteudo e follow-up.",
        "order": 2,
    },
    {
        "id": LeadStatus.HANDOFF_PENDING.value,
        "name": "Atendimento",
        "description": "Leads WARM aguardando especialista humano.",
        "order": 3,
    },
    {
        "id": LeadStatus.HANDOFF_PENDING_URGENT.value,
        "name": "Urgente",
        "description": "Leads HOT com prioridade maxima.",
        "order": 4,
    },
    {
        "id": LeadStatus.CONSOLIDATED.value,
        "name": "Consolidados",
        "description": "Leads vendidos, resolvidos ou finalizados com sucesso.",
        "order": 5,
    },
    {
        "id": LeadStatus.DEAD.value,
        "name": "Perdidos",
        "description": "Leads sem continuidade comercial.",
        "order": 6,
    },
]


class MoveLeadStageRequest(BaseModel):
    status: LeadStatus = Field(..., description="Nova etapa operacional do lead.")
    notes: Optional[str] = Field(default=None, description="Observacao opcional para o time.")


class QualifyLeadRequest(BaseModel):
    message: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=2000,
        description=(
            "Mensagem a qualificar. Se omitida, o CRM usa a ultima mensagem do lead."
        ),
    )


def _status_value(status) -> str:
    return getattr(status, "value", status)


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _serialize_lead(lead: Lead) -> dict:
    return {
        "id": lead.phone_number,
        "phone_number": lead.phone_number,
        "name": lead.name,
        "goal": lead.current_goal,
        "score": lead.current_score,
        "status": _status_value(lead.status),
        "notes": lead.notes,
        "is_repeated": lead.is_repeated,
        "source": lead.source,
        "created_at": _serialize_datetime(lead.created_at),
        "last_interaction": _serialize_datetime(lead.last_interaction),
    }


def _serialize_interaction(interaction: Interaction) -> dict:
    return {
        "id": interaction.id,
        "phone_number": interaction.phone_number,
        "role": interaction.role,
        "content": interaction.content,
        "timestamp": _serialize_datetime(interaction.timestamp),
    }


def _get_or_create_lead(db: Session, phone_number: str) -> Lead:
    lead = db.query(Lead).filter(Lead.phone_number == phone_number).first()
    if lead:
        return lead

    lead = Lead(phone_number=phone_number, source="crm")
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _get_latest_user_message(interactions: list[Interaction]) -> Optional[str]:
    for interaction in reversed(interactions):
        if interaction.role == "user":
            return interaction.content
    return None


def _stage_for_result(score: Optional[str], next_action: Optional[str]) -> LeadStatus:
    if score == "HOT":
        return LeadStatus.HANDOFF_PENDING_URGENT
    if score == "WARM":
        return LeadStatus.HANDOFF_PENDING
    if score == "COLD" or next_action == "NURTURE":
        return LeadStatus.MARKETING_NURTURE
    return LeadStatus.NEW


@router.get("", response_class=HTMLResponse)
async def crm_home():
    return """
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>CRM Eleva</title>
    <style>
      body { margin: 0; font-family: Arial, sans-serif; background: #f3f4f6; color: #111827; }
      header { padding: 20px 28px; background: #fff; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center; }
      main { padding: 24px; }
      h1 { margin: 0; font-size: 28px; }
      .muted { color: #6b7280; font-size: 14px; margin-top: 4px; }
      .toolbar { display: flex; gap: 8px; align-items: center; }
      button { border: 1px solid #111827; background: #111827; color: #fff; border-radius: 8px; padding: 10px 14px; cursor: pointer; }
      input { border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 12px; min-width: 300px; }
      .board { display: flex; gap: 16px; overflow-x: auto; padding-bottom: 16px; }
      .column { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; min-width: 300px; width: 300px; padding: 14px; }
      .column h2 { margin: 0; font-size: 17px; }
      .lead { margin-top: 12px; border: 1px solid #e5e7eb; border-radius: 8px; background: #f9fafb; padding: 12px; }
      .lead strong { display: block; margin-bottom: 6px; }
      .badge { display: inline-block; border-radius: 999px; padding: 3px 8px; background: #e5e7eb; font-size: 12px; margin-top: 8px; }
      .empty { margin-top: 12px; color: #9ca3af; font-size: 14px; }
      .error { color: #b91c1c; margin: 16px 0; }
    </style>
  </head>
  <body>
    <header>
      <div>
        <h1>CRM Eleva</h1>
        <div class="muted">Qualificacao de leads com agentes de IA</div>
      </div>
      <div class="toolbar">
        <input id="phone" placeholder="Telefone/ID do lead" />
        <input id="message" placeholder="Mensagem para qualificar" />
        <button onclick="qualifyLead()">Qualificar</button>
        <button onclick="loadBoard()">Atualizar</button>
      </div>
    </header>
    <main>
      <div id="error" class="error"></div>
      <section id="board" class="board"></section>
    </main>
    <script>
      async function loadBoard() {
        const error = document.getElementById("error");
        const board = document.getElementById("board");
        error.textContent = "";
        board.innerHTML = "";

        try {
          const response = await fetch("/crm/kanban");
          const payload = await response.json();
          payload.data.forEach((column) => {
            const el = document.createElement("article");
            el.className = "column";
            el.innerHTML = `<h2>${column.name}</h2><div class="muted">${column.leads.length} leads</div>`;

            if (!column.leads.length) {
              el.innerHTML += `<div class="empty">Sem leads nesta etapa.</div>`;
            }

            column.leads.forEach((lead) => {
              const card = document.createElement("div");
              card.className = "lead";
              card.innerHTML = `
                <strong>${lead.name || lead.phone_number}</strong>
                <div class="muted">${lead.goal || "Objetivo nao classificado"}</div>
                <span class="badge">${lead.score || "UNKNOWN"}</span>
                <div class="muted">${lead.notes || ""}</div>
              `;
              el.appendChild(card);
            });

            board.appendChild(el);
          });
        } catch (err) {
          error.textContent = "Nao foi possivel carregar o CRM.";
        }
      }

      async function qualifyLead() {
        const phone = document.getElementById("phone").value.trim();
        const message = document.getElementById("message").value.trim();
        const error = document.getElementById("error");
        error.textContent = "";

        if (!phone || !message) {
          error.textContent = "Informe telefone/ID e mensagem do lead.";
          return;
        }

        const response = await fetch(`/crm/leads/${encodeURIComponent(phone)}/qualify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message })
        });

        if (!response.ok) {
          error.textContent = "Nao foi possivel qualificar o lead.";
          return;
        }

        document.getElementById("message").value = "";
        await loadBoard();
      }

      loadBoard();
    </script>
  </body>
</html>
"""


@router.get("/stages")
async def get_crm_stages():
    return {"status": "success", "data": CRM_STAGES}


@router.get("/kanban")
async def get_crm_kanban(db: Session = Depends(get_db)):
    leads = db.query(Lead).order_by(Lead.last_interaction.desc()).all()
    columns = [
        {
            **stage,
            "leads": [
                _serialize_lead(lead)
                for lead in leads
                if _status_value(lead.status) == stage["id"]
            ],
        }
        for stage in CRM_STAGES
    ]

    return {
        "status": "success",
        "count": len(leads),
        "data": columns,
    }


@router.get("/leads/{phone_number}")
async def get_crm_lead(phone_number: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.phone_number == phone_number).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado.")

    interactions = (
        db.query(Interaction)
        .filter(Interaction.phone_number == phone_number)
        .order_by(Interaction.timestamp.asc())
        .all()
    )

    return {
        "status": "success",
        "data": {
            **_serialize_lead(lead),
            "interactions": [_serialize_interaction(item) for item in interactions],
        },
    }


@router.patch("/leads/{phone_number}/stage")
async def move_crm_lead_stage(
    phone_number: str,
    payload: MoveLeadStageRequest,
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(Lead.phone_number == phone_number).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead nao encontrado.")

    lead.status = payload.status
    lead.last_interaction = datetime.utcnow()
    if payload.notes is not None:
        lead.notes = payload.notes

    db.commit()
    db.refresh(lead)

    return {"status": "success", "data": _serialize_lead(lead)}


@router.post("/leads/{phone_number}/qualify")
async def qualify_crm_lead(
    phone_number: str,
    payload: QualifyLeadRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    lead = _get_or_create_lead(db, phone_number)

    interactions = (
        db.query(Interaction)
        .filter(Interaction.phone_number == phone_number)
        .order_by(Interaction.timestamp.asc())
        .all()
    )
    history = [{"role": item.role, "content": item.content} for item in interactions]

    message = payload.message or _get_latest_user_message(interactions)
    if not message:
        raise HTTPException(
            status_code=400,
            detail="Informe uma mensagem para qualificar este lead.",
        )

    if payload.message:
        user_message = Interaction(
            id=str(uuid4()),
            phone_number=phone_number,
            role="user",
            content=payload.message,
        )
        db.add(user_message)
        db.commit()

    orchestrator: Orchestrator = request.app.state.orchestrator
    result = await orchestrator.handle(
        message=message,
        history=history,
        current_goal=lead.current_goal,
        is_repeated=bool(interactions) or lead.is_repeated,
    )

    score = result.get("lead_score", {}).get("score", "UNKNOWN")
    goal = result.get("classification", {}).get("goal", lead.current_goal)
    strategy = result.get("strategy") or {}
    response_text = result.get("sdr_response")
    trace_id = result.get("trace_id") or str(uuid4())

    lead.current_score = score
    lead.current_goal = goal
    lead.status = _stage_for_result(score, strategy.get("next_action"))
    lead.is_repeated = True
    lead.last_interaction = datetime.utcnow()

    if strategy.get("reasoning"):
        lead.notes = strategy["reasoning"]

    if response_text:
        db.add(
            Interaction(
                id=trace_id,
                phone_number=phone_number,
                role="assistant",
                content=response_text,
            )
        )

    db.commit()
    db.refresh(lead)

    return {
        "status": "success",
        "data": {
            "lead": _serialize_lead(lead),
            "qualification": result,
        },
    }
