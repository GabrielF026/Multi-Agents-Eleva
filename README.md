# Multi-Agents-Eleva
Repositorio criado para o sistama de multiagentes desenvolvidos para a eleva credi


Multi-Agents Eleva
Arquitetura de IA para Qualificação e Priorização de Leads
🎯 Objetivo do Sistema

O Multi-Agents Eleva é um sistema de IA projetado para:

Classificar intenção de leads

Recomendar o produto adequado

Avaliar temperatura do lead (HOT, WARM, COLD)

Definir prioridade operacional

Encaminhar para atendimento humano estratégico

Preparar base para follow-up automático

O sistema não fecha vendas no MVP.
Ele qualifica e direciona.

🧠 Arquitetura Geral

O sistema utiliza arquitetura multi-agentes com orquestração centralizada.

Fluxo principal:

Mensagem do Cliente
        ↓
GoalClassifierAgent
        ↓
LeadScoreAgent
        ↓
SDRAgent
        ↓
StrategyEngine
        ↓
Resposta estruturada + estratégia operacional
🧩 Componentes do Sistema
1️⃣ GoalClassifierAgent

Responsável por identificar o objetivo do lead.

Categorias atuais:

FINANCIAMENTO

CREDITO_ALTO

ALUGAR_IMOVEL

NEGOCIAR_DIVIDAS

LIMPAR_NOME

OUTRO

Estratégia:

Regras rápidas (baixo custo)

Fallback via LLM

Retorno:

{
  "goal": "LIMPAR_NOME",
  "source": "rule" | "llm"
}
2️⃣ LeadScoreAgent

Responsável por classificar temperatura do lead:

HOT → pronto para ação

WARM → interessado com dúvidas

COLD → baixa intenção

Estratégia híbrida:

Palavras-chave (regra rápida)

Classificação via LLM

Retorno:

{
  "lead_score": "WARM",
  "source": "rule_warm" | "rule_hot" | "llm"
}
3️⃣ SDRAgent

Responsável por gerar resposta estratégica baseada em:

Objetivo (goal)

Produto recomendado

Temperatura do lead (lead_score)

Comportamento adaptativo:
Lead Score	Estratégia de Comunicação
HOT	Direto, objetivo, encaminhamento imediato
WARM	Consultivo, empático, pergunta estratégica
COLD	Leve, sem pressão

O SDR não fecha vendas no MVP.

4️⃣ StrategyEngine

Camada de decisão operacional.

Define:

next_action

priority

followup

Encaminhamento humano

Regras atuais:
Lead Score	Next Action	Priority
HOT	HANDOFF_TO_HUMAN	HIGH
WARM	HANDOFF_TO_HUMAN	MEDIUM
COLD	NURTURE	LOW

Exemplo de retorno final:

{
  "strategy": {
    "lead_score": "WARM",
    "next_action": "HANDOFF_TO_HUMAN",
    "priority": "MEDIUM",
    "followup": {
      "enabled": true,
      "delay_days": 2
    }
  }
}
🏗️ Orchestrator

Responsável por coordenar os agentes.

Ordem atual:

Classificar objetivo

Classificar temperatura

Gerar resposta SDR

Aplicar estratégia final

Arquivo:

app/orchestrator/orchestrator.py
📦 Estrutura de Pastas
app/
 ├── agents/
 │    ├── goalclassifier.py
 │    ├── sdr_agent.py
 │    ├── lead_score_agent.py
 │
 ├── core/
 │    ├── base_agent.py
 │    ├── llm_provider.py
 │    ├── product_catalog.py
 │
 ├── infrastructure/
 │    ├── openai_provider.py
 │
 ├── orchestrator/
 │    ├── orchestrator.py
 │
 ├── strategy/
 │    ├── strategy_engine.py
 │
 ├── main.py
⚙️ Tecnologias

Python 3.11

FastAPI

Async Architecture

OpenAI API

Docker

Docker Compose

🚀 Status Atual do MVP

✅ Arquitetura multi-agentes implementada
✅ Classificação de objetivo funcional
✅ Scoring híbrido funcional
✅ SDR adaptativo por temperatura
✅ Strategy Engine com priorização
✅ Encaminhamento humano estruturado
⚠️ Persistência de leads ainda não implementada
⚠️ Follow-up automático ainda não implementado
⚠️ Banco de dados ainda não estruturado

🧠 Próximas Fases
Sprint 2

Modelagem da entidade Lead

Configuração de banco (PostgreSQL)

Persistência no Orchestrator

Migration com Alembic

Sprint 3

Conversation + Message

State machine

Follow-up automático real

Sprint 4

Dashboard operacional

Fila por prioridade

Métricas de conversão

🎯 Filosofia do Projeto

O sistema é orientado a:

Inteligência estratégica

Modularidade

Separação de responsabilidades

Evolução incremental

Baixo acoplamento

Cada agente possui responsabilidade única.
O Orchestrator controla o fluxo.
O StrategyEngine separa inteligência de decisão operacional.

🔐 Importante

Este MVP:

Não fecha vendas.

Não envia link de pagamento.

Não substitui humano.

Não executa ações externas.

Ele qualifica, organiza e prioriza.