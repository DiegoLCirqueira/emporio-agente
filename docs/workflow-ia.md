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

### 2026-11-01 — Decisões do Diego

- **Diego aceitou as recomendações** de abordagem, dados, interface e guardrails.
- **Diego ajustou o que o agente propôs:**
  - **Políticas:** sem RAG, mas com citação da seção de origem e testes dos fatos críticos.
  - **Provedor:** só o Anthropic agora; Gemini vira bônus opcional (o agente havia proposto os dois adaptadores desde o início).
  - **Avaliação:** de ~25 para 12–15 cenários e2e, sem LLM-as-judge.
  - **Promoções:** acrescentou que o agente nunca promete desconto inativo, mesmo que o PDF fale de Black Friday.
- **Diego aceitou as decisões de dados 1 a 7.** Nos itens 8 e 9 ele não se manifestou, e o Orchestrator adotou a recomendação, marcada como revisável em `docs/decisoes.md`.
- **Diego pediu:**
  - criar o repositório público no GitHub e fazer push ao fim de cada etapa;
  - incluir no README uma seção "Tratamento e qualidade dos dados".
- **Orchestrator:** criou o repositório com `gh repo create` (público) e fez o push dos 6 commits. Registrou as decisões em `docs/decisoes.md`, a fonte de verdade para os agentes.

### 2026-11-01 — Passo 3: estrutura

- **Orchestrator:** despachou em paralelo, em arquivos disjuntos para evitar conflito:
  - **Python:** pyproject, src/, tests/, `.env.example`, `.gitignore`, `.gitattributes`, venv e teste de fumaça em TDD.
  - **Docs/QA:** esqueleto do README.

  Os agentes não fazem operações git; o Orchestrator revisa e comita.
- **Python:**
  - escreveu o teste de fumaça antes do código e o viu falhar (`AttributeError`) antes de criar `__init__.py`;
  - validou com um teste temporário que os e2e são pulados quando não há chave de API;
  - deixou de fora o `readme` do `pyproject.toml` para a instalação não quebrar enquanto o README não existia;
  - propôs a árvore de módulos para a implementação.
- **Docs/QA:** escreveu o esqueleto do README com as 9 seções e marcou como pendente tudo o que ainda não existe.
- **Orchestrator:**
  - rodou o pytest de forma independente (1 passed);
  - adicionou `readme` ao `pyproject.toml`;
  - preencheu "Como rodar" com os comandos reais;
  - **corrigiu uma imprecisão do README**, que dizia que o Diego "removeu o RAG". O RAG nunca foi a recomendação: o Diego confirmou a decisão sem RAG e acrescentou citações de seção e testes dos fatos.
- **Pendências de implementação registradas:** o `conftest.py` ainda não lê o `.env`, e falta decidir onde fica o `politicas.md` (package-data ou caminho do repo).

### 2026-11-01 — Implementação, rodada 1 (itens 1 a 5)

- **Diego decidiu:**
  - `politicas.md` dentro do pacote, como package data;
  - o `config.py` lê o `.env`, e os e2e continuam pulados sem chave;
  - aceitou DD8 e DD9 e pediu que a divergência dos pedidos 3 e 20 seja citada no README.
- **Diego acrescentou requisitos às ferramentas, cada um com teste:**
  - busca tolerante a variações de nome ("takamine gd 20");
  - pergunta ao cliente quando houver ambiguidade;
  - preços em `Decimal` formatados como R$ 1.234,56;
  - erros estruturados, nunca exceções cruas;
  - teste específico de não vazamento de PII.
- **Diego definiu o ponto de controle:** parar depois da CLI, antes dos e2e, para ele avaliar o agente conversando com ele.
- **Orchestrator:**
  - registrou os requisitos como I1–I8 em `docs/decisoes.md` e configurou o package-data no `pyproject.toml`;
  - despachou em paralelo, em arquivos disjuntos:
    - **Python:** itens 1, 2, 3 e 5 (config, dados, ferramentas, provedor Anthropic). O Python comita os próprios arquivos com caminhos explícitos, com um commit verde por ciclo TDD que registra o vermelho no corpo, e faz push por item.
    - **AI Engineer:** item 4 (`politicas.md` curado com citação de seção, `politicas.py` com o system prompt e os testes dos fatos críticos). Os commits do AI Engineer ficam com o Orchestrator.
- **Decisão de processo do Orchestrator:** cada commit fica verde, com teste e implementação juntos, em vez de um commit separado com o teste falhando. Assim a `main` nunca fica quebrada, e a evidência do vermelho fica no corpo da mensagem.
