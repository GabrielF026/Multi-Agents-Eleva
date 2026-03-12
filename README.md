# 🤖 Multi-Agents Eleva

Sistema de qualificação de leads baseado em pipeline de agentes de IA.
Desenvolvido para a **Eleva**, focada em soluções de crédito e recuperação financeira.

---

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Pipeline de Agentes](#pipeline-de-agentes)
- [Estrutura de Pastas](#estrutura-de-pastas)
- [Tecnologias](#tecnologias)
- [Como Rodar Localmente](#como-rodar-localmente)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Endpoints da API](#endpoints-da-api)
- [Exemplos de Requisição](#exemplos-de-requisição)
- [Fluxo de Dados](#fluxo-de-dados)
- [Catálogo de Produtos](#catálogo-de-produtos)
- [Guia de Contribuição — Fase 2](#guia-de-contribuição--fase-2)
- [Roadmap](#roadmap)

---

## Visão Geral

Este projeto implementa um sistema de qualificação de leads usando um **pipeline de agentes de IA**.  
A partir de uma mensagem enviada pelo cliente, o sistema:

- Classifica o **objetivo** do cliente (ex.: FINANCIAMENTO, LIMPAR_NOME, etc.)
- Classifica a **temperatura do lead** (HOT, WARM, COLD)
- Gera uma **resposta humanizada** via um SDR virtual
- Define uma **estratégia operacional** (handoff para humano, nutrição, follow-up)

Toda a jornada é rastreada por um `trace_id` único por requisição.

---

## Arquitetura

```text
┌─────────────────────────────────────────────────────────┐
│                        FastAPI                          │
│                       main.py                           │
│         POST /chat          GET /health                 │
└───────────────────────┬─────────────────────────────────┘
                        │ AgentContext
                        ▼
┌─────────────────────────────────────────────────────────┐
│                     Orchestrator                        │
│   Coordena o pipeline · Logging · Resiliência           │
└──┬──────────────┬──────────────┬───────────────────────┘
   │              │              │
   ▼              ▼              ▼
┌──────────┐ ┌─────────────┐ ┌──────────┐
│  Goal    │ │  LeadScore  │ │   SDR    │
│Classifier│ │   Agent     │ │  Agent   │
│  Agent   │ │             │ │          │
└──────────┘ └─────────────┘ └──────────┘
   │              │              │
   └──────────────┴──────────────┘
                  │ AgentContext enriquecido
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   StrategyEngine                        │
│   HANDOFF_TO_HUMAN · NURTURE · Follow-up config        │
└─────────────────────────────────────────────────────────┘
```

### Princípios

- **AgentContext imutável**: todos os agentes recebem e retornam um `AgentContext` via `model_copy(update=...)`.
- **Interface única** entre agentes: `async def run(self, context: AgentContext) -> AgentContext`.
- **Plug and play**: adicionar um novo agente é só colocá-lo na lista em `main.py`.
- **Resiliência**: falhas são registradas em `context.errors` e o pipeline continua.
- **Rastreabilidade**: cada requisição tem um `trace_id` propagado por todos os agentes.

---

## Pipeline de Agentes

```text
Mensagem do cliente
        │
        ▼
┌───────────────────────┐
│  GoalClassifierAgent  │
│ - Regras rápidas      │
│ - Fallback LLM com    │
│   structured output   │
│ → context.goal        │
│ → context.goal_source │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│   LeadScoreAgent      │
│ - Regras HOT/WARM/COLD│
│ - Fallback LLM com    │
│   reasoning + schema  │
│ → context.lead_score  │
│ → context.lead_score_ │
│    source             │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│      SDRAgent         │
│ - System prompt (persona)  │
│ - User prompt (tarefa atual)│
│ - Considera histórico +     │
│   is_repeated               │
│ → context.sdr_response      │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│    StrategyEngine     │
│ - HANDOFF_TO_HUMAN    │
│ - NURTURE             │
│ - Follow-up + priority│
│ → context.strategy    │
└───────────┬───────────┘
            │
            ▼
Resposta final com trace_id
```

---

## Estrutura de Pastas

```text
MULTI-AGENTS-ELEVA/
│
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── goalclassifier.py      # Classifica objetivo do lead
│   │   ├── lead_score_agent.py    # Classifica temperatura HOT/WARM/COLD
│   │   └── sdr_agent.py           # Gera resposta consultiva
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base_agent.py          # BaseAgent: run(context), logging comum
│   │   ├── context.py             # AgentContext e LeadData (Pydantic)
│   │   ├── llm_provider.py        # Interface abstrata de LLM
│   │   └── product_catalog.py     # Catálogo tipado de produtos Eleva
│   │
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   └── openai_provider.py     # Provedor OpenAI com retry e timeout
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── action.py
│   │   ├── base.py
│   │   ├── classification.py
│   │   ├── conversation.py
│   │   ├── enums.py
│   │   ├── lead.py
│   │   ├── lead_interest.py
│   │   └── message.py
│   │
│   ├── orchestrator/
│   │   └── orchestrator.py        # Coordena o pipeline de agentes
│   │
│   ├── strategy/
│   │   └── strategy_engine.py     # Motor de decisão operacional
│   │
│   └── main.py                    # FastAPI: endpoints, DI, middleware
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## Tecnologias

| Tecnologia | Uso |
|-----------|-----|
| Python 3.11+ | Linguagem principal |
| FastAPI | API assíncrona |
| Pydantic v2 | Modelos e validação |
| OpenAI Python SDK | Chamada ao GPT-4o-mini (ou compatível) |
| Tenacity | Retry com exponential backoff |
| Uvicorn | ASGI server |

---

## Como Rodar Localmente

### 1. Clonar o repositório

```bash
git clone https://github.com/<seu-usuario>/multi-agents-eleva.git
cd multi-agents-eleva
```

### 2. Criar e ativar ambiente virtual

```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie um `.env` na raiz (ou exporte no seu ambiente):

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini        # opcional (default)
OPENAI_TIMEOUT=30.0             # opcional (default em segundos)
```

### 5. Rodar o servidor

```bash
uvicorn app.main:app --reload
```

Acesse:

- Swagger/OpenAPI: http://localhost:8000/docs  
- Health: http://localhost:8000/health

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|----------|------------|-----------|
| `OPENAI_API_KEY` | ✅ | API key da OpenAI |
| `OPENAI_MODEL` | ❌ | Modelo usado (default: `gpt-4o-mini`) |
| `OPENAI_TIMEOUT` | ❌ | Timeout em segundos (default: `30.0`) |

---

## Endpoints da API

### `GET /health`

Health check real — verifica o provider de LLM e os agentes registrados.

**Resposta (exemplo):**

```json
{
  "status": "ok",
  "llm_available": true,
  "agents_registered": [
    "GoalClassifierAgent",
    "LeadScoreAgent",
    "SDRAgent"
  ],
  "agent_count": 3,
  "version": "1.0.0"
}
```

Se o LLM estiver indisponível, retorna status HTTP `503`.

---

### `POST /chat`

Executa o pipeline completo para uma mensagem do cliente.

**Request body:**

```json
{
  "message": "Quero limpar meu nome no Serasa, está sujo há 2 anos.",
  "history": [],
  "current_goal": null,
  "is_repeated": false
}
```

Campos:

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|------------|-----------|
| `message` | string | ✅ | Mensagem atual do cliente (máx. ~2000 chars) |
| `history` | lista de objetos | ❌ | Histórico no formato `[{ "role": "user"|"assistant", "content": "..." }]` |
| `current_goal` | string | ❌ | Goal identificado anteriormente (se a conversa já existia) |
| `is_repeated` | boolean | ❌ | Se o lead já teve contato anterior com a Eleva |

**Response (exemplo simplificado):**

```json
{
  "trace_id": "3f7a1c2e-...",
  "classification": {
    "goal": "LIMPAR_NOME",
    "source": "rule"
  },
  "lead_score": {
    "score": "WARM",
    "source": "rule_warm"
  },
  "sdr_response": "Entendo, ficar com o nome sujo tanto tempo é bem desconfortável...",
  "strategy": {
    "trace_id": "3f7a1c2e-...",
    "lead_score": "WARM",
    "goal": "LIMPAR_NOME",
    "next_action": "HANDOFF_TO_HUMAN",
    "priority": "HIGH",
    "followup": {
      "enabled": true,
      "delay_days": 2,
      "reason": "Lead WARM: interesse real detectado. Follow-up em 2 dias..."
    },
    "reasoning": "Lead WARM com objetivo 'LIMPAR_NOME': interesse real..."
  },
  "pipeline_errors": [],
  "has_errors": false
}
```

---

## Exemplos de Requisição

### Lead HOT

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quanto custa para limpar meu nome? Preciso resolver hoje.",
    "history": [],
    "is_repeated": false
  }'
```

### Lead WARM

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Meu nome está sujo há 2 anos e o banco recusou meu crédito.",
    "history": [],
    "is_repeated": false
  }'
```

### Lead com histórico

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Quanto fica no total?",
    "history": [
      { "role": "user", "content": "Quero limpar meu nome" },
      { "role": "assistant", "content": "Olá! Posso te ajudar com isso." }
    ],
    "current_goal": "LIMPAR_NOME",
    "is_repeated": false
  }'
```

---

## Fluxo de Dados

```text
POST /chat
    │
    │  ChatRequest (Pydantic)
    ▼
Orchestrator.handle()
    │
    │  AgentContext { trace_id, lead: LeadData }
    ▼
GoalClassifierAgent.run()
    │  → goal, goal_source
    ▼
LeadScoreAgent.run()
    │  → lead_score, lead_score_source
    ▼
SDRAgent.run()
    │  → sdr_response
    ▼
StrategyEngine.apply()
    │  → strategy
    ▼
Resposta consolidada (JSON) com trace_id
```

Garantias:

- `AgentContext` é imutável (`frozen=True`).
- Agentes não lançam exceções não tratadas; erros vão para `context.errors`.
- Se o LLM estiver indisponível, o Orchestrator retorna uma resposta de fallback segura.
- Cada decisão (goal, score, estratégia) traz um `source` (`rule`, `llm`, `fallback`).

---

## Catálogo de Produtos

O catálogo fica em `app/core/product_catalog.py` e é tipado via Pydantic.

Produtos ativos no MVP:

| Key                | Nome                                   | Goals indicados                                  | Status |
|--------------------|----------------------------------------|--------------------------------------------------|--------|
| `RAIO_X_FINANCEIRO`| Raio-X Financeiro                      | FINANCIAMENTO, CREDITO_ALTO, OUTRO               | ✅ Ativo |
| `LIMPA_NOME`       | Limpa Nome e Suspensão das Dívidas     | LIMPAR_NOME, NEGOCIAR_DIVIDAS, ALUGAR_IMOVEL     | ✅ Ativo |

Produtos já modelados para fase 2 (inativos):

- `RATING_BANCARIO`
- `LIMPA_BACEN`
- `CONSORCIO`
- `HOME_EQUITY`

Cada produto possui:

- `name`
- `description`
- `differentials`
- `price` (estrutura `ProductPrice` com tipo FIXED/INSTALLMENT/ON_DEMAND)
- `indicated_for` (lista de `GoalType`)
- `active` (bool)

O `SDRAgent` usa esses dados para contextualizar a resposta.

---

## Guia de Contribuição — Fase 2

### 1. Adicionar um novo Goal

1. Atualize o enum em `app/core/product_catalog.py`:

```python
class GoalType(str, Enum):
    FINANCIAMENTO = "FINANCIAMENTO"
    CREDITO_ALTO = "CREDITO_ALTO"
    ALUGAR_IMOVEL = "ALUGAR_IMOVEL"
    NEGOCIAR_DIVIDAS = "NEGOCIAR_DIVIDAS"
    LIMPAR_NOME = "LIMPAR_NOME"
    OUTRO = "OUTRO"
    NOME_LIMPO_SEM_CREDITO = "NOME_LIMPO_SEM_CREDITO"  # novo
```

2. Adicione regras no `GoalClassifierAgent` para esse goal.

3. Mapeie o goal para um produto no `ProductCatalog`.

---

### 2. Adicionar um agente especialista por produto

1. Crie o arquivo do agente em `app/agents/`:

```python
class FinanciamentoSpecialistAgent(BaseAgent):
    def __init__(self, llm_provider):
        super().__init__(llm_provider, name="FinanciamentoSpecialistAgent", ...)

    async def run(self, context: AgentContext) -> AgentContext:
        if context.goal != "FINANCIAMENTO":
            return context
        # lógica especialista
        return context.model_copy(update={...})
```

2. Registre o agente em `app/main.py`:

```python
agents = [
    GoalClassifierAgent(llm_provider=llm_provider),
    LeadScoreAgent(llm_provider=llm_provider),
    FinanciamentoSpecialistAgent(llm_provider=llm_provider),  # novo
    SDRAgent(llm_provider=llm_provider),
]
```

3. (Opcional) Conecte o produto a esse agente no `ProductCatalog` via um campo futuro `specialist_agent`.

---

### 3. Boas práticas de commit

Sugestão de prefixos:

- `feat(agent): ...`
- `fix(goal-classifier): ...`
- `refactor(orchestrator): ...`
- `docs(readme): ...`
- `chore(deps): ...`
- `test(lead-score): ...`

---

## Roadmap

### MVP — Fase 1 ✅

- [x] Pipeline: GoalClassifier → LeadScore → SDR
- [x] StrategyEngine com HANDOFF e NURTURE
- [x] AgentContext imutável com `trace_id`
- [x] LLM provider com retry, timeout e structured output
- [x] ProductCatalog tipado
- [x] Health check real
- [x] Logging estruturado por agente

### Fase 2 — Agentes Especialistas 🔜

- [ ] Novos goals (ex.: `NOME_LIMPO_SEM_CREDITO`, `RESTRICAO_BACEN`, etc.)
- [ ] Agentes especialistas por produto (Rating, Bacen, Consórcio, Home Equity)
- [ ] Router de agentes baseado em goal e produto
- [ ] Persistência de leads e histórico em banco de dados
- [ ] Dashboard operacional com rastreio por `trace_id`

### Fase 3 — Escala 🔮

- [ ] Engine de follow-up automático
- [ ] Integração com CRM (HubSpot / RD Station)
- [ ] Integração com WhatsApp Business API
- [ ] Observabilidade com OpenTelemetry
- [ ] Fine-tuning de modelo especializado no domínio Eleva