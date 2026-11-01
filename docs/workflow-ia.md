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

### 2026-11-01 — Passo 1: exploração dos dados

- **Orchestrator:** dividiu o trabalho em duas frentes paralelas:
  - **Python:** perfil estatístico dos 6 CSVs, com o script reproduzível `scripts/explorar_dados.py` (só stdlib).
  - **AI Engineer:** leitura do PDF de políticas, papel de cada tabela no atendimento e mapeamento de PII.
- **Correção:** o primeiro despacho falhou antes de chegar aos agentes, por um erro de escape (`\U`) no caminho Windows dentro do script que monta o lote de mensagens. O Orchestrator trocou o caminho por barras normais e reenviou.
- **Achados que mudam o desenho do agente:**
  - Os dados estão limpos no formato; os problemas são semânticos: promoções sem vigência, `status` e estoque contraditórios, totais de pedido que não batem com os itens, e-mail duplicado entre clientes e pedidos defasados em relação à data de hoje.
  - O AI Engineer mostrou que extrair o PDF com `pdftotext -layout` **troca os horários** da tabela (Sábado aparece como 09h–18h). A leitura sem `-layout` dá o correto: seg–sex 09h–18h, sáb 09h–13h. Esse erro só apareceu porque as extrações foram comparadas.
  - O PDF tem contradições internas: dois WhatsApps, parcela mínima divergente e base de prazo de garantia inconsistente.
- **Orchestrator:** revisou e rodou o script do Python antes de comitar e enviou o perfil ao AI Engineer para a consolidação em `docs/exploracao-dados.md`.
- **AI Engineer:** consolidou os dois relatórios em `docs/exploracao-dados.md` (18 problemas ordenados por impacto) e reconciliou uma divergência aparente entre os relatórios. No pedido 20, um citava os preços (689 + 799) e o outro os ids dos produtos (107 e 84). Os dois estavam certos.

### 2026-11-01 — Passo 2: opções de arquitetura

- **AI Engineer:** escreveu `docs/opcoes-arquitetura.md` com 2 ou 3 opções por decisão, prós e contras, uma recomendação e 10 decisões de dados em aberto. Os preços dos modelos foram conferidos nas páginas oficiais e marcados como "não verificado" quando a confirmação não foi possível.
- **Orchestrator:** fez uma verificação independente, sem confiar no relatório:
  - reextraiu o horário do PDF;
  - conferiu no CSV os exemplos do golden set (pedido 8 → cliente 2, telefone e rastreio; preços do Takamine GD20 e do Crafter HT-100);
  - confirmou o preço do Claude Haiku 5.5 ($0.10 / $0.50 por 1M tokens) na página oficial de pricing da Anthropic.

  Tudo bateu. Créditos grátis para contas novas continuam como não verificados.
- **Status:** aguardando as escolhas do Diego. Nenhuma implementação foi iniciada.
