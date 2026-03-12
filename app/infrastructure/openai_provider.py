# app/infrastructure/openai_provider.py

import os
import json
import logging
from typing import Type, TypeVar, Any, List, Dict

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.llm_provider import LLMProviderInterface, LLMResponse

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProviderInterface):
    """
    Implementação concreta de LLMProviderInterface usando OpenAI.

    Implementa os três métodos abstratos da interface:
    - health_check
    - generate_structured
    - generate_with_history
    """

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY não definida nas variáveis de ambiente"
            )

        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        timeout_env = os.getenv("OPENAI_TIMEOUT", "30.0")

        try:
            self.timeout = float(timeout_env)
        except ValueError:
            self.timeout = 30.0

        self.client = AsyncOpenAI(api_key=api_key)
        self.logger = logger.getChild("OpenAIProvider")

        self.logger.info(
            "OpenAIProvider inicializado",
            extra={
                "model": self.model,
                "timeout": self.timeout,
            },
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        try:
            await self._ping()
            self.logger.info("openai_health_check_ok")
            return True
        except Exception as e:
            self.logger.error(
                "openai_health_check_failed",
                extra={"error": str(e)},
            )
            return False

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
    )
    async def _ping(self) -> None:
        await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            timeout=self.timeout,
        )

    # ------------------------------------------------------------------
    # Structured output — GoalClassifier e LeadScoreAgent
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        temperature: float = 0.0,
        extra_messages: List[Dict[str, Any]] | None = None,
    ) -> T:
        """
        Gera resposta estruturada como JSON e valida com Pydantic.

        A OpenAI exige que o prompt contenha a palavra 'json' quando
        response_format=json_object é usado. Por isso injetamos uma
        instrução de sistema garantindo isso sempre.

        Em caso de ValidationError, tenta adaptar chaves alternativas
        antes de lançar exceção — evitando fallback_error desnecessário.
        """
        system_message = {
            "role": "system",
            "content": (
                "Você é um classificador preciso. "
                "Sempre responda em formato JSON válido "
                "seguindo exatamente o schema solicitado. "
                "Use apenas as chaves especificadas no schema, "
                "sem adicionar campos extras."
            ),
        }

        messages: List[Dict[str, str]] = [system_message]

        if extra_messages:
            messages.extend(extra_messages)

        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=600,
            response_format={"type": "json_object"},
            timeout=self.timeout,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Resposta vazia do modelo em generate_structured")

        # Tenta validação direta primeiro
        try:
            return schema.model_validate_json(content)

        except ValidationError as ve:
            self.logger.warning(
                "generate_structured_validation_error_trying_adapter",
                extra={
                    "error": str(ve),
                    "raw_content": content[:500],
                    "schema": schema.__name__,
                },
            )

            # Tenta adaptar o JSON antes de desistir
            try:
                data = json.loads(content)
                adapted = self._adapt_json(data, schema)
                result = schema.model_validate(adapted)
                self.logger.info(
                    "generate_structured_adapted_successfully",
                    extra={
                        "schema": schema.__name__,
                        "original_keys": list(data.keys()),
                        "adapted_keys": list(adapted.keys()),
                    },
                )
                return result

            except Exception as adapt_err:
                self.logger.error(
                    "generate_structured_adaptation_failed",
                    extra={
                        "error": str(adapt_err),
                        "raw_content": content[:500],
                        "schema": schema.__name__,
                    },
                )
                raise ve  # Re-lança o erro original de validação

        except Exception as e:
            self.logger.error(
                "generate_structured_unexpected_error",
                extra={
                    "error": str(e),
                    "raw_content": content[:500],
                },
            )
            raise

    def _adapt_json(self, data: dict, schema: Type[T]) -> dict:
        """
        Tenta adaptar um JSON com chaves alternativas para o schema esperado.

        Cobre casos onde o modelo responde com sinônimos ou nomes em português.
        Mapeamento: {chave_alternativa: chave_do_schema}
        """
        adapted = dict(data)

        # Mapeamento de aliases conhecidos → campo correto do schema
        alias_map = {
            # LeadScoreOutput
            "lead_score": "score",
            "temperatura": "score",
            "temperature": "score",
            "classificacao": "score",
            "classificação": "score",
            "nivel": "score",
            "nível": "score",
            "motivo": "reasoning",
            "reason": "reasoning",
            "justificativa": "reasoning",
            "explicacao": "reasoning",
            "explicação": "reasoning",
            "confianca": "confidence",
            "confiança": "confidence",
            "nivel_confianca": "confidence",
            "nível_confiança": "confidence",

            # GoalClassification
            "objetivo": "goal",
            "intencao": "goal",
            "intenção": "goal",
            "goal_type": "goal",
            "categoria": "goal",
            "raciocinio": "reasoning",
            "raciocínio": "reasoning",
            "nivel_confianca": "confidence",
        }

        for alias, canonical in alias_map.items():
            if alias in adapted and canonical not in adapted:
                adapted[canonical] = adapted.pop(alias)

        # Garante campos obrigatórios com defaults se ainda faltarem
        schema_fields = schema.model_fields
        for field_name, field_info in schema_fields.items():
            if field_name not in adapted:
                # Tenta inferir valor padrão
                if field_name == "confidence":
                    adapted[field_name] = "medium"
                elif field_name == "reasoning":
                    adapted[field_name] = "Classificado pelo modelo."
                else:
                    adapted[field_name] = ""

        return adapted

    # ------------------------------------------------------------------
    # Geração com histórico — SDRAgent
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
    )
    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 600,
    ) -> LLMResponse:
        """
        Gera texto livre considerando o histórico completo.
        Retorna LLMResponse com .content para o SDRAgent consumir.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.timeout,
        )

        content = response.choices[0].message.content or ""

        self.logger.info(
            "generate_with_history_ok",
            extra={
                "messages_count": len(messages),
                "response_length": len(content),
            },
        )

        return LLMResponse(content=content)