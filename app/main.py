# app/main.py
from dotenv import load_dotenv
load_dotenv()
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agents.goalclassifier import GoalClassifierAgent
from app.agents.lead_score_agent import LeadScoreAgent
from app.agents.sdr_agent import SDRAgent
from app.infrastructure.openai_provider import OpenAIProvider
from app.infrastructure.meta_provider import MetaAPIProvider
from app.services.meta_service import MetaService
from app.orchestrator.orchestrator import Orchestrator
from app.routers import crm, webhooks
from app.infrastructure.database import Base, engine, SessionLocal
from app.models.database_models import Lead

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Lifespan — inicialização e encerramento controlados
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    Tudo dentro do bloco antes do yield é executado no startup.
    Tudo depois do yield é executado no shutdown.

    Isso garante que:
    - Dependências são criadas UMA vez, de forma controlada
    - Erros de configuração (ex: API key ausente) falham no startup,
      não na primeira requisição
    - Recursos são liberados corretamente no shutdown
    """
    logger.info("Iniciando aplicação Eleva Multi-Agents...")

    # 1. Inicializa o provider de LLM
    #    Se OPENAI_API_KEY não estiver definida, falha aqui com mensagem clara
    llm_provider = OpenAIProvider()

    # 2. Gera as tabelas no PostgreSQL (AWS) caso não existam
    Base.metadata.create_all(bind=engine)
    
    # 3. Monta a lista de agentes em ordem de execução
    #    Para adicionar um novo agente na fase 2:
    #    basta incluir nessa lista — sem tocar no Orchestrator
    agents = [
        GoalClassifierAgent(llm_provider=llm_provider),
        LeadScoreAgent(llm_provider=llm_provider),
        SDRAgent(llm_provider=llm_provider),
    ]

    # 3. Inicializa o Orchestrator com as dependências injetadas
    orchestrator = Orchestrator(
        agents=agents,
        llm_provider=llm_provider,
    )

    # 4. Disponibiliza o orchestrator para todos os endpoints via app.state
    app.state.orchestrator = orchestrator

    # 5. Inicializa módulos da Meta
    meta_provider = MetaAPIProvider()
    meta_service = MetaService(orchestrator, meta_provider)
    app.state.meta_service = meta_service

    logger.info(
        "Aplicação inicializada com sucesso",
        extra={"agents": [a.name for a in agents]}
    )

    yield  # aplicação rodando

    # Shutdown
    logger.info("Encerrando aplicação Eleva Multi-Agents...")


# ------------------------------------------------------------------
# Aplicação FastAPI
# ------------------------------------------------------------------

app = FastAPI(
    title="Eleva Multi-Agents API",
    description=(
        "Sistema de qualificação e recuperação de crédito "
        "baseado em agentes de IA."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(webhooks.router)
app.include_router(crm.router)


# ------------------------------------------------------------------
# Middleware — Request ID e logging de requisições
# ------------------------------------------------------------------

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    """
    Middleware executado em toda requisição.

    Responsabilidades:
    - Gera um request_id único para rastreamento
    - Loga início e fim de cada requisição com latência
    - Injeta request_id no header de resposta

    O request_id aparece nos logs junto com o trace_id dos agentes,
    permitindo correlacionar a requisição HTTP com o pipeline interno.
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.time()

    logger.info(
        "request_started",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }
    )

    response = await call_next(request)

    duration_ms = round((time.time() - start_time) * 1000, 2)

    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
    )

    # Injeta request_id no header de resposta
    # Permite ao cliente correlacionar logs com suporte
    response.headers["X-Request-ID"] = request_id

    return response


# ------------------------------------------------------------------
# Handler global de erros inesperados
# ------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Captura qualquer exceção não tratada.

    Garante que o cliente sempre receba uma resposta JSON estruturada
    ao invés de um erro 500 genérico do FastAPI.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    logger.critical(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "error": str(exc),
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Erro interno inesperado.",
            "request_id": request_id,
            "detail": "Nossa equipe foi notificada. Tente novamente em instantes.",
        }
    )


# ------------------------------------------------------------------
# Schemas de request e response
# ------------------------------------------------------------------

class ChatRequest(BaseModel):
    """
    Payload de entrada do endpoint /chat.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Mensagem atual do cliente.",
        examples=["Quero limpar meu nome no Serasa"],
    )
    history: list[dict] = Field(
        default_factory=list,
        description=(
            "Histórico de mensagens anteriores da conversa. "
            "Formato: [{'role': 'user'|'assistant', 'content': '...'}]"
        ),
    )
    current_goal: Optional[str] = Field(
        default=None,
        description="Objetivo identificado em interações anteriores.",
    )
    is_repeated: bool = Field(
        default=False,
        description="True se o cliente já teve contato anterior com a Eleva.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Quero limpar meu nome no Serasa, está sujo há 2 anos.",
                    "history": [],
                    "current_goal": None,
                    "is_repeated": False,
                },
                {
                    "message": "Quanto custa? Preciso resolver hoje.",
                    "history": [
                        {"role": "user", "content": "Quero limpar meu nome"},
                        {"role": "assistant", "content": "Olá! Posso te ajudar com isso."},
                    ],
                    "current_goal": "LIMPAR_NOME",
                    "is_repeated": False,
                },
            ]
        }
    }


class HealthResponse(BaseModel):
    """Schema de resposta do endpoint /health."""
    status: str
    llm_available: bool
    agents_registered: list[str]
    agent_count: int
    version: str


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Verifica saúde da aplicação e disponibilidade do LLM.",
    tags=["Sistema"],
)
async def health_check(request: Request):
    """
    Endpoint de saúde real — verifica o Orchestrator e o LLM.

    Retorna 200 se tudo ok, 503 se o LLM estiver indisponível.
    Usado por Docker healthcheck, load balancers e monitoramento.
    """
    orchestrator: Orchestrator = request.app.state.orchestrator
    health = await orchestrator.health_check()

    status_code = (
        status.HTTP_200_OK
        if health["llm_available"]
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=status_code,
        content={**health, "version": app.version},
    )


@app.post(
    "/chat",
    summary="Qualificação de Lead",
    description=(
        "Recebe a mensagem do cliente e executa o pipeline completo: "
        "classificação de objetivo → scoring → resposta SDR → estratégia operacional."
    ),
    tags=["Agentes"],
)
async def chat(request: Request, payload: ChatRequest):
    """
    Endpoint principal do sistema.

    Fluxo:
        1. Valida payload via Pydantic
        2. Chama Orchestrator com todos os parâmetros de contexto
        3. Retorna resultado consolidado com trace_id

    O trace_id no response permite correlacionar com logs internos.
    """
    orchestrator: Orchestrator = request.app.state.orchestrator

    result = await orchestrator.handle(
        message=payload.message,
        history=payload.history,
        current_goal=payload.current_goal,
        is_repeated=payload.is_repeated,
    )

    return result

@app.get(
    "/leads",
    summary="Listar Leads",
    description="Retorna a lista de leads mapeados no banco de dados AWS. Uso interno operacional.",
    tags=["Operacional"],
)
async def get_leads():
    # Segurança: Numa implementação mais severa o ideal seria proteger com DEPENDS(JWT)
    # Por hora extrairemos num escopo fechado p/ o MVP.
    db = SessionLocal()
    try:
        leads = db.query(Lead).all()
        return {
            "status": "success",
            "count": len(leads),
            "data": [
                 {
                     "phone_number": l.phone_number,
                     "name": l.name,
                     "goal": l.current_goal,
                     "score": l.current_score,
                     "status": getattr(l.status, "value", l.status),
                     "notes": l.notes,
                     "last_interaction": l.last_interaction
                 } for l in leads
            ]
        }
    finally:
        db.close()
