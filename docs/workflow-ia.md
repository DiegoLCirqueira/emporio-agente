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
- **Correção:** o segundo despacho também falhou antes de chegar aos agentes, desta vez por aspas dentro de um heredoc no shell. Os prompts passaram a ser gravados em arquivo com a ferramenta de escrita.
- **AI Engineer (item 4):**
  - curou o `politicas.md` com a seção de origem em cada trecho e notas de curadoria para DD2, DD4, DD5 e DD6;
  - escreveu o `politicas.py` com o prompt dividido em parte estável (cache) e variável (data);
  - escreveu 29 testes de fatos críticos.

  O Orchestrator conferiu os fatos no PDF (CNPJ, endereço, prazos, campanhas) e comitou.
- **Correção do Orchestrator, em TDD:** o prompt mandava usar a data "para saber se a loja está aberta", mas o agente não recebe a hora. O Orchestrator escreveu um teste falhando e trocou a instrução: o agente informa o horário do dia em vez de afirmar que a loja está aberta.
- **Python (itens 1, 2, 3 e 5):**
  - 7 commits, cada um com o vermelho registrado no corpo, e 179 testes na suíte inteira;
  - busca tolerante com radical, junção de tokens ("gd" + "20") e fallback por difflib;
  - erro idêntico para pedido inexistente e identificação errada (anti-enumeração);
  - teste de PII com mais de 150 chamadas, validado por mutação: com o e-mail sem máscara, o teste quebra.

  O Python listou 10 escolhas técnicas não previstas em `docs/decisoes.md`. O Orchestrator as aceitou e registrou como T1–T10, revisáveis pelo Diego.
- **Incidente de processo:** o Python terminou à 01h28, mas o `maestri ask` de retorno falhou por aspas no shell (relatório longo inline), e o terminal ficou preso. O Orchestrator só percebeu às 12h28, quando foi checar. Resultado: cerca de 11 horas de prazo paradas. Os commits já estavam no remoto, então nada se perdeu além do tempo.
  - **Mitigação:** os relatórios passam a ser escritos em arquivo (`.relatorio-*.md`, ignorado pelo git), e o `ask` de retorno só leva o caminho.
  - **Lição:** um despacho longo precisa de checagem periódica (`maestri check`), não só da espera pela notificação.

### 2026-11-01 — Implementação, rodada 2 (itens 6 e 7)

- **Orchestrator:** conferiu as ferramentas à mão (Takamine GD20, pedido 8 com e sem identificação válida, promoção do 90, acessório, ferramenta inexistente) e despachou ao Python o agente (loop, janela de histórico, fallbacks) e a CLI (`--mensagem`, `--mostrar-ferramentas`, transcripts). A parada antes dos e2e continua mantida.
- **Bloqueio identificado:** não há chave de API na máquina. A rodada 2 é testada só com fakes, e o Diego precisa criar o `.env` antes do ponto de controle.
- **Python:** fez 4 commits e a suíte chegou a 217 testes. O protocolo de retorno por arquivo funcionou na primeira tentativa.
  - **Agente:** loop com no máximo 5 iterações, janela cortada só em fala do cliente, turno com erro técnico descartado do histórico e `ferramentas_chamadas` vindo do resultado real das ferramentas, para servir de base aos e2e.
  - **CLI:** REPL, `-m`, `--mostrar-ferramentas`, `--debug` e transcripts.
  - **Vermelho real encontrado no TDD:** com a pasta de dados inexistente, a CLI mostrava um traceback. Foi corrigido para sair com código 2 e mensagem clara.
  - Listou 7 escolhas a confirmar. A mais relevante: os transcripts guardam o telefone ou e-mail que o cliente digitou. Eles ficam fora do git, mas as conversas de exemplo precisam de revisão antes de entrar no repositório.
- **Orchestrator:** rodou a suíte (217 passed) e a CLI sem chave (exit 2 com instrução de configuração).
- **Ainda não verificado contra a API real:** o adaptador Anthropic foi testado só com cliente falso. O ponto de controle do Diego é o primeiro teste real.
- **Ponto de controle:** a implementação parou antes dos e2e, como o Diego pediu.

### 2026-11-01 — Ponto de controle

- **Diego decidiu:**
  - mudar o filtro de preço da busca para o preço final com promoção (T2), com teste obrigatório do caso tabela acima do limite e promocional abaixo;
  - registrar as 7 escolhas pendentes do agente e da CLI;
  - rodar um roteiro de 12 conversas reais com critérios definidos por ele, sem corrigir comportamento antes do relatório.
- **Orchestrator:**
  - registrou T12–T18 e revisou T2 em `docs/decisoes.md`, apontando que o filtro era a T2, não a T3 citada no pedido;
  - verificou que não havia chave de API na máquina (nem `.env` nem variável de ambiente) e pediu ao Diego que criasse o `.env`, sem manipular o segredo.
- **Python:** fez a mudança do filtro em TDD (`cbb5467`), com 3 falhas vistas no vermelho e 5 testes novos (produtos 90 e 121, o inverso com `preco_min`, produto sem promoção e produto só com promoções inativas). A suíte passou para 222 testes. O Orchestrator conferiu à mão que o 90 aparece com teto de R$ 2.000.

### 2026-11-01 — Mudança de provedor: Gemini no free tier

- **Diego decidiu:** nenhuma API paga. O provedor principal passa a ser o Gemini no free tier do Google AI Studio. Isso inverte a D4 (Haiku 5.5 padrão, Gemini como bônus) e antecipa o adaptador Gemini, antes previsto só para o fim do dia 2.
- **Diego pediu:**
  - adaptador em TDD com o SDK oficial em versão estável com pelo menos 2 semanas de lançamento;
  - `EMPORIO_PROVEDOR` com padrão `gemini`;
  - modelo `gemini-3.8-flash`, confirmado na documentação oficial;
  - retry com espera exponencial em 429;
  - registro de que o adaptador Anthropic não foi validado com chamadas reais;
  - o roteiro de 12 conversas rodado com o Gemini.
- **Regra de segredos:** nenhuma chave aparece em transcrições, logs, diário, commits ou relatórios. O Orchestrator confirmou só a presença das variáveis no `.env`: `GEMINI_API_KEY` definida, `ANTHROPIC_API_KEY` vazia e `.env` ignorado pelo git. Notou que o `.env` do Diego ainda tem `EMPORIO_MODELO=claude-haiku-5-5` e não tem `EMPORIO_PROVEDOR`.
- **Orchestrator:** despachou em paralelo:
  - **Python:** adaptador Gemini, config, retry, `.env.example` e um teste de fumaça real com no máximo 3 requisições;
  - **AI Engineer:** verificação em fontes oficiais do Google (free tier do modelo, limites RPM/RPD, termos de uso de dados, exigência de cartão).

  O roteiro de 12 conversas fica para depois do adaptador.
- **AI Engineer (pesquisa):**
  - confirmou em fontes oficiais que o `gemini-3.8-flash` está no free tier, é Stable e suporta function calling;
  - confirmou o Flash-Lite `gemini-3.5-flash-lite`, os termos de uso de dados (uso para melhoria dos produtos e revisão humana), a ausência de exigência de cartão e o Brasil entre as regiões atendidas;
  - os limites RPM/RPD **não são publicados** e só aparecem no AI Studio, logado.
- **Python:**
  - adaptador Gemini em TDD com `google-genai` 2.31.0 (a versão estável mais nova com pelo menos 2 semanas; as 2.32 a 2.34 foram descartadas pela regra);
  - devolução da `thought_signature` no histórico, retry em 429/5xx e `COTA_ESGOTADA` com mensagem própria;
  - 265 testes.

  O teste de fumaça real pegou 503/504 do serviço.
- **Orchestrator:**
  - varreu o repositório e o histórico em busca de chaves (nenhuma);
  - reescreveu a D4 em `docs/decisoes.md` e registrou T19–T22;
  - despachou o README ao Docs/QA (revisado e comitado) e o roteiro real ao AI Engineer;
  - quando a conversa 3 falhou com 503/504 no `gemini-3.8-flash`, pediu um diagnóstico para separar sobrecarga do serviço de defeito do adaptador: uma rodada com o Flash-Lite e o tempo de cada erro medido.
- **Roteiro real (AI Engineer):**
  - **Gemini 3.8 Flash:** as 12 chamadas falharam, com 503 em ~3 s (sobrecarga) e 504 em ~60 s (prazo).
  - **Flash-Lite:** funcionou. O function calling real ficou validado, sem nenhum 400. As 12 conversas rodaram com ele, em 39 requisições no total e sem nenhum 429.
  - **Resultado:** 7 ✅, 3 ⚠️, 2 ❌ e **nenhum vazamento de PII**, verificado pelo AI Engineer e de novo, de forma independente, pelo Orchestrator.
  - **Falhas:** o agente afirmou "estamos abertos" sem saber a hora (o modelo ignorou a T11) e inventou "pedido já entregue" a partir da previsão vencida.
  - **Parciais:**
    - a busca corta em 10 por ordem de id e deixa um item mais barato de fora;
    - "tem promoções ativas" foi afirmado sem chamar a ferramenta;
    - "palheta" foi resolvida pela política, sem ferramenta, o que é discutível contra o critério.
  - Nada foi corrigido, conforme o Diego pediu.
