# 🤖 Multi-Agents-Eleva

Sistema de **qualificação de leads com múltiplos agentes de IA**, desenvolvido para a ElevaCredi. Processa mensagens de WhatsApp e Instagram, qualifica leads automaticamente e alimenta o CRM com dados estruturados.

---

## Visão Geral

```
[WhatsApp / Instagram]
         │ webhook Meta API
         ▼
┌─────────────────────────────────────────────┐
│           PIPELINE DE AGENTES               │
│                                             │
│  GoalClassifier → LeadScoreAgent → SDRAgent │
│       ↓               ↓              ↓      │
│   Identifica      HOT/WARM/COLD    Responde │
│   o produto       + reasoning      o lead   │
└─────────────────────────────────────────────┘
         │
         ▼
   PostgreSQL (leads + interactions)
         │
         ▼
   REST API /crm/* → CRM ElevaCredi
```

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework | FastAPI (Python 3.11+) |
| Agentes IA | OpenAI GPT-4o-mini |
| Banco de dados | PostgreSQL + SQLAlchemy |
| Container | Docker + docker-compose |
| Canais | Meta API (WhatsApp Business + Instagram) |

---

## Agentes

### `GoalClassifier`
Identifica o **objetivo/produto** do lead com base na conversa.

**Produtos suportados:**
- `LIMPAR_NOME` — Limpeza de nome / renegociação
- `PORTABILIDADE` — Portabilidade de crédito
- `EMPRESTIMO_PESSOAL` — Empréstimo pessoal
- `FGTS` — Antecipação de FGTS
- `CONSORCIO` — Consórcio
- `REFINANCIAMENTO` — Refinanciamento
- `CARTAO_CONSIGNADO` — Cartão consignado

### `LeadScoreAgent`
Classifica a temperatura do lead: **HOT / WARM / COLD**

- Regras por keywords (sem custo de LLM)
- Fallback LLM para casos ambíguos
- Nunca rebaixa um score — só mantém ou sobe
- Bypass automático para pedidos de atendimento humano

### `SDRAgent`
Gera a resposta ao lead, com tom consultivo e orientado à conversão. Adapta o script ao objetivo identificado e à temperatura do lead.

---

## API REST

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/crm/kanban` | Leads agrupados por etapa |
| `GET` | `/crm/stages` | Lista de etapas do funil |
| `GET` | `/crm/leads/{phone}` | Detalhes do lead + histórico |
| `PATCH` | `/crm/leads/{phone}/stage` | Move lead de etapa |
| `POST` | `/crm/leads/{phone}/qualify` | Qualifica manualmente |
| `GET` | `/webhooks/meta` | Verificação do webhook Meta |
| `POST` | `/webhooks/meta` | Recebe eventos WhatsApp/Instagram |

---

## Setup Local

### Pré-requisitos
- Docker + Docker Compose
- Conta Meta for Developers (WhatsApp Business API)
- Chave da OpenAI API

### 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite `.env`:
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

META_VERIFY_TOKEN=seu_token
META_ACCESS_TOKEN=seu_access_token
WHATSAPP_PHONE_ID=id_do_numero
INSTAGRAM_ACCOUNT_ID=id_da_conta

DATABASE_URL=postgresql://user:password@db:5432/eleva
```

### 2. Subir os containers

```bash
docker-compose up --build
```

API disponível em: `http://localhost:8000`  
Docs interativos: `http://localhost:8000/docs`

### 3. Testar qualificação

```bash
curl -X POST http://localhost:8000/crm/leads/5511999999999/qualify \
  -H "Content-Type: application/json" \
  -d '{"message": "Oi, tenho uma dívida no Nubank de 8 mil reais, como vocês podem me ajudar?"}'
```

---

## Etapas do Funil

| Status interno | Nome | Descrição |
|---|---|---|
| `NEW` | Prospecção IA | Lead recebido, ainda não qualificado |
| `MARKETING_NURTURE` | Nutrição | Lead frio em fluxo de follow-up |
| `HANDOFF_PENDING` | Atendimento Humano | Lead WARM aguardando especialista |
| `HANDOFF_PENDING_URGENT` | Urgente | Lead HOT — prioridade máxima |
| `CONSOLIDATED` | Venda Efetivada | Lead convertido com sucesso |
| `DEAD` | Perdido | Sem continuidade comercial |

---

## Estrutura do Projeto

```
app/
├── agents/           # GoalClassifier, LeadScoreAgent, SDRAgent
├── core/             # BaseAgent, AgentContext, LLMProvider
├── infrastructure/   # Configuração do banco de dados
├── models/           # Modelos SQLAlchemy (Lead, Interaction)
├── orchestrator/     # Pipeline de orquestração dos agentes
├── routers/          # Endpoints FastAPI (crm.py, webhooks.py)
├── rules/            # Regras de negócio estáticas
├── schemas/          # Schemas Pydantic
├── services/         # MetaService (WhatsApp/Instagram)
└── main.py           # Entry point FastAPI
```

---

## Relacionado

- 📊 **[ElevaCredi CRM](https://github.com/seu-usuario/elevacredi-crm)** — Interface visual do funil de vendas
- 🔗 **[ElevaCredi Platform](https://github.com/seu-usuario/elevacredi-platform)** — Monorepo de integração

---

> Desenvolvido para **ElevaCredi** — Soluções de crédito potencializadas por IA