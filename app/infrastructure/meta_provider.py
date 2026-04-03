import os
import logging
import httpx

logger = logging.getLogger(__name__)

class MetaAPIProvider:
    """
    Provedor responsável pela comunicação com a Graph API da Meta.
    Encapsula chamadas HTTP para o WhatsApp.
    """
    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN")
        self.phone_id = os.getenv("WHATSAPP_PHONE_ID")
        self.ig_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.api_version = "v18.0" # ou mais recente
        self.wa_base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_id}/messages"
        self.ig_base_url = f"https://graph.facebook.com/{self.api_version}/{self.ig_account_id}/messages"
        
        if not self.access_token:
            logger.warning("META_ACCESS_TOKEN não configurado. Integração Meta falhará.")

    async def send_whatsapp_message(self, to: str, message: str) -> dict:
        """
        Envia uma mensagem de texto simples pelo WhatsApp usando a Graph API.
        """
        if not self.access_token:
            raise ValueError("O token de acesso da Meta não foi configurado.")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.wa_base_url,
                    json=payload,
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info("send_whatsapp_message_success", extra={"to": to, "message_id": data.get("messages", [{}])[0].get("id")})
                return data
            except httpx.HTTPStatusError as e:
                logger.error("send_whatsapp_message_http_error", extra={"status_code": e.response.status_code, "text": e.response.text})
                raise
            except Exception as e:
                logger.error("send_whatsapp_message_error", extra={"error": str(e)})
                raise

    async def send_instagram_message(self, to: str, message: str) -> dict:
        """
        Envia uma DM pelo Instagram usando a Graph API.
        """
        if not self.access_token:
            raise ValueError("O token de acesso da Meta não foi configurado.")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "recipient": {"id": to},
            "message": {"text": message}
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.ig_base_url,
                    json=payload,
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info("send_instagram_message_success", extra={"to": to})
                return data
            except httpx.HTTPStatusError as e:
                logger.error("send_instagram_message_http_error", extra={"status_code": e.response.status_code, "text": e.response.text})
                raise
            except Exception as e:
                logger.error("send_instagram_message_error", extra={"error": str(e)})
                raise
