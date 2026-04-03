import os
import re
import logging
from typing import Optional

from app.infrastructure.meta_provider import MetaAPIProvider
from app.orchestrator.orchestrator import Orchestrator
from app.infrastructure.database import SessionLocal
from app.models.database_models import Lead, Interaction, LeadStatus

logger = logging.getLogger(__name__)

class MetaService:
    """
    Camada de serviço que cruza os dados do Webhook da Meta com o Orquestrador local,
    mantendo persistência de segurança pelo Banco de Dados.
    Trata mensagens tanto do WhatsApp Oficial quanto do Instagram Directs.
    Também funciona como BOT Handoff para o WhatsApp da Empresa.
    """
    def __init__(self, orchestrator: Orchestrator, meta_provider: MetaAPIProvider):
        self.orchestrator = orchestrator
        self.meta_provider = meta_provider
        self.company_number = os.getenv("COMPANY_WHATSAPP_NUMBER", "5511999999999") # Altere no .env

    async def process_whatsapp_message(self, payload: dict):
        """
        Extrai as infos do payload do WhatsApp e repassa para o handler core.
        """
        try:
            entry = payload.get("entry", [])
            if not entry: return
            changes = entry[0].get("changes", [])
            if not changes: return
            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            
            if not messages: return
            
            msg_obj = messages[0]
            phone_number = msg_obj.get("from")
            text_body = msg_obj.get("text", {}).get("body", "")
            
            if not phone_number or not text_body: return
            
            logger.info("whatsapp_message_received", extra={"phone": phone_number})
            await self._process_and_reply(source="whatsapp", identifier=phone_number, text_body=text_body)
            
        except Exception as e:
            logger.error("process_whatsapp_message_error", extra={"error": str(e)}, exc_info=True)

    async def process_instagram_message(self, payload: dict):
        """
        Extrai as infos do payload do Instagram DM e repassa para o handler core.
        """
        try:
            entry = payload.get("entry", [])
            if not entry: return
            messaging = entry[0].get("messaging", [])
            if not messaging: return
            
            event = messaging[0]
            sender_id = event.get("sender", {}).get("id")
            text_body = event.get("message", {}).get("text", "")
            
            if not sender_id or not text_body: return
            
            logger.info("instagram_message_received", extra={"ig_id": sender_id})
            await self._process_and_reply(source="instagram", identifier=sender_id, text_body=text_body)
            
        except Exception as e:
            logger.error("process_instagram_message_error", extra={"error": str(e)}, exc_info=True)


    async def _process_and_reply(self, source: str, identifier: str, text_body: str):
        """
        Motor core: Lê db, gera IA e envia de volta na plataforma correta.
        """
        db = SessionLocal()
        try:
            # 1. Busca o Lead Seguro no BD
            lead = db.query(Lead).filter(Lead.phone_number == identifier).first()
            is_repeated = False
            
            if lead:
                is_repeated = True
                current_goal = lead.current_goal
            else:
                # O identifier serve tanto para o nº do WPP quanto para o ID do IG
                lead = Lead(phone_number=identifier, source=source)
                db.add(lead)
                db.commit()
                db.refresh(lead)
                current_goal = None

            # -------------------------------------------------------------
            # EXTRATOR DE NOME (Falha 2 corrigida)
            # -------------------------------------------------------------
            if not lead.name:
                msg_lower = text_body.lower()
                name_match = re.search(r"(?:meu nome é|sou (?:o|a)|me chamo|aqui é[\\s|o|a]*)\s*([A-Za-zÀ-ÖØ-öø-ÿ]+)", msg_lower)
                if name_match:
                    lead.name = name_match.group(1).capitalize()
                elif len(text_body.split()) <= 2 and not any(kw in msg_lower for kw in ["não", "sim", "oi", "ola", "olá", "quero", "preciso", "qual", "quanto"]):
                    # Se mandou apenas 1 ou 2 palavras cruas (provavelmente respondendo com o próprio nome)
                    lead.name = text_body.title()

            # 2. Puxa o histórico
            past_interactions = db.query(Interaction).filter(Interaction.phone_number == identifier).order_by(Interaction.timestamp).all()
            history_list = [{"role": i.role, "content": i.content} for i in past_interactions]

            # Salva interação do usuário
            user_msg = Interaction(phone_number=identifier, role="user", content=text_body, id=f"user-{len(history_list)}")
            db.add(user_msg)
            db.commit()

            # 3. Disparar Pipeline de IA
            result = await self.orchestrator.handle(
                message=text_body,
                history=history_list,
                current_goal=current_goal,
                is_repeated=is_repeated
            )
            
            # Trilha e Atualizar Status do DB baseado no retorno
            score = result.get("lead_score", {}).get("score", "UNKNOWN") if isinstance(result.get("lead_score"), dict) else "UNKNOWN"
            goal = result.get("classification", {}).get("goal", current_goal) if isinstance(result.get("classification"), dict) else current_goal
            strategy_data = result.get("strategy", {})
            trace_id = result.get("trace_id", "unknown-trace")
            response_text = result.get("sdr_response", "Desculpe, ocorreu um erro interno.")
            
            # Salva a resposta da IA no histórico
            assistant_msg = Interaction(phone_number=identifier, role="assistant", content=response_text, id=trace_id)
            db.add(assistant_msg)

            # Atualiza Lead 
            lead.current_score = score
            lead.current_goal = goal
            
            # FUNIL OPERACIONAL:
            action = strategy_data.get("next_action")
            
            if score == "COLD" or action == "NURTURE":
                lead.status = LeadStatus.MARKETING_NURTURE
                lead.notes = "Lead COLD. Entrou em trilha de Marketing. Follow-up futuramente."
            
            elif score == "WARM":
                lead.status = LeadStatus.HANDOFF_PENDING
                lead.notes = "Cliente precisa de mais informações para fechar (Lead Morno)."
                await self._notify_company_bot(lead, strategy_data)

            elif score == "HOT":
                lead.status = LeadStatus.HANDOFF_PENDING_URGENT
                lead.notes = "Prioridade absoluta. Atenda o cliente da melhor maneira possível."
                await self._notify_company_bot(lead, strategy_data)

            db.commit()

            # 4. Enviar a resposta via Meta API para o Cliente de acordo com o canal
            if source == "whatsapp":
                await self.meta_provider.send_whatsapp_message(to=identifier, message=response_text)
            elif source == "instagram":
                await self.meta_provider.send_instagram_message(to=identifier, message=response_text)

        finally:
            db.close()

    async def _notify_company_bot(self, lead: Lead, strategy_data: dict):
        """
        BOT interno: Manda notificação do lead pro número do WhatsApp do time de vendas.
        """
        nome = lead.name if lead.name else "Nome não captado ainda"
        plataforma_visual = "🟢 WhatsApp" if lead.source == "whatsapp" else "🟣 Instagram"
        
        relatorio = (
            f"🚨 *NOVO LEAD QUALIFICADO ({plataforma_visual})* 🚨\n\n"
            f"👤 *Nome:* {nome}\n"
            f"📱 *Contato/ID:* {lead.phone_number}\n"
            f"🔥 *Temperatura:* {lead.current_score}\n"
            f"🎯 *Interesse (Goal):* {lead.current_goal}\n"
            f"📋 *Observação:* {lead.notes}\n\n"
            f"🤖 *IA reporta:* {strategy_data.get('reasoning', '')}"
        )
        try:
            # O Handoff SEMPRE vai para o WhatsApp da Empresa, independente de onde o lead veio
            await self.meta_provider.send_whatsapp_message(to=self.company_number, message=relatorio)
            logger.info("Notificação Handoff disparada com sucesso para empresa.")
        except Exception as e:
            logger.error("Falha ao notificar time de vendas", extra={"error": str(e)})
