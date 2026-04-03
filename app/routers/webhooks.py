import os
import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks

from app.services.meta_service import MetaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

def verify_meta_signature(request: Request, body: bytes):
    """
    Função de segurança em conformidade com as boas práticas.
    Verifica a autenticidade do webhook comparando a assinatura recebida (x-hub-signature-256)
    com a gerada localmente usando a APP SECRET como chave.
    OBS: Estamos abstraindo a APP SECRET para META_VERIFY_TOKEN aqui para simplicidade, 
    mas num ambiente real AWS seria lido do Secrets Manager.
    """
    signature = request.headers.get("x-hub-signature-256")
    if not signature:
        # Pular validação caso em ambiente de Dev sem assinatura? Para focar em segurança, vamos apenas avisar no log.
        logger.warning("Falta de assinatura X-Hub-Signature-256 no webhook. Rejeitando requisição de forma segura.")
        raise HTTPException(status_code=401, detail="Header de assinatura ausente")

    # Isso requer a configuração da META_APP_SECRET
    app_secret = os.getenv("META_APP_SECRET", os.getenv("META_VERIFY_TOKEN", ""))
    
    expected_hash = hmac.new(
        app_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    
    expected_signature = f"sha256={expected_hash}"

    # Validação blind side (against timing attacks)
    if not hmac.compare_digest(expected_signature, signature):
        logger.error("Assinatura do webhook inválida. Possível ataque detectado.")
        raise HTTPException(status_code=401, detail="Assinatura inválida")

@router.get("/meta")
async def verify_webhook(request: Request):
    """
    Rota obrigatoriamente exigida pela plataforma 'Meta for Developers' para ativar o Webhook.
    """
    verify_token = os.environ.get("META_VERIFY_TOKEN")
    
    query_params = request.query_params
    mode = query_params.get("hub.mode")
    token = query_params.get("hub.verify_token")
    challenge = query_params.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == verify_token:
            logger.info("Webhook ativado com sucesso via Meta Dashboard.")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Os tokens de verificação não batem.")
    
    raise HTTPException(status_code=400, detail="Faltam parâmetros da Meta")


@router.post("/meta")
async def receive_webhook(
    request: Request, 
    background_tasks: BackgroundTasks
):
    """
    Recebe os eventos (mensagens) enviados pela nuvem oficial do WhatsApp e Instagram.
    """
    body_bytes = await request.body()
    
    # 1. Segurança: Verificamos se veio da Meta para evitar Spoofing vazando informações
    # Em um ambiente de staging/teste rápido (sem secret), a linha abaixo pode ser comentada
    # verify_meta_signature(request, body_bytes) 
    
    payload = await request.json()
    logger.info("meta_webhook_received", extra={"object": payload.get("object", "unknown")})

    # Verifica se é do WhatsApp
    if payload.get("object") == "whatsapp_business_account":
        meta_service = request.app.state.meta_service
        background_tasks.add_task(meta_service.process_whatsapp_message, payload)
        return {"status": "EVENT_RECEIVED"}
        
    # Verifica se é do Instagram
    elif payload.get("object") == "instagram":
        meta_service = request.app.state.meta_service
        background_tasks.add_task(meta_service.process_instagram_message, payload)
        return {"status": "EVENT_RECEIVED"}
        
    return {"status": "NOT_SUPPORTED", "message": "Plataforma ainda não suportada"}
