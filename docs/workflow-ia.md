# Diário de workflow com IA

Registro de como os assistentes de código foram usados neste projeto: quem fez o quê, quais decisões o Diego tomou, quais o agente propôs e onde houve correção. Este diário vira a seção "Uso de assistentes de código" do README.

## Setup

- **Ferramenta:** Claude Code, rodando no Maestri (canvas com vários terminais de agentes conectados).
- **Banda:**
  - **Orchestrator:** recebe as instruções do Diego, decompõe o trabalho, delega e integra os resultados. É o único agente com quem o Diego fala.
  - **AI Engineer:** exploração dos dados e propostas de arquitetura do agente.
  - **Python:** estrutura do projeto e implementação em TDD.
  - **Docs/QA:** README, documentação e verificação.
- **Regra de governança:** o Diego toma as decisões de arquitetura. Os agentes propõem opções com prós, contras e uma recomendação.

## Registro

### 2026-11-01 — Kickoff

- **Diego:** definiu as regras do projeto (commits pequenos sem reescrita de histórico, TDD, segredos em `.env`, este diário, decisões de arquitetura com ele) e o plano em três passos: exploração, decisões e estrutura.
- **Orchestrator:** encontrou os materiais apenas em um zip em `Downloads/` e perguntou onde criar o repositório.
  - **Diego decidiu:** criar em `C:\Users\Arthur\emporio-agente`.
  - **Orchestrator propôs e Diego aceitou:** extrair o texto do PDF do enunciado para `docs/desafio.md` (com `pdftotext`) em vez de colar manualmente.
- **Orchestrator:** fez `git init`, copiou os dados originais para `data/` sem alteração e fez o commit inicial.
