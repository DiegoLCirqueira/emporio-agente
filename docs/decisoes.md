# Decisões tomadas

Decisões do Diego em 2026-11-01 sobre as opções de `docs/opcoes-arquitetura.md`. Este arquivo é a fonte de verdade para a implementação. Uma mudança aqui exige nova decisão do Diego.

## Arquitetura

| # | Tema | Decisão |
|---|---|---|
| D1 | Abordagem | Function calling com loop próprio sobre o SDK do provedor, sem LangChain/LangGraph. Máximo de 5 iterações de ferramenta por turno. |
| D2 | Dados | Ferramentas específicas por intenção sobre `csv` + `Decimal` em memória (stdlib), com as regras de negócio no código. Ferramentas: `buscar_produtos`, `detalhar_produto`, `consultar_pedido`, `listar_promocoes_ativas` e, opcionalmente, `calcular_pagamento`. Nenhuma ferramenta lista ou busca clientes. |
| D3 | Políticas | `politicas.md` curado à mão, inteiro no system prompt (com prompt caching), **sem RAG**. Cada trecho cita a seção do PDF de origem (ex.: "§4.1"). Testes automatizados confirmam os fatos críticos: horário de cada dia, prazos de troca, devolução e garantia, regras de parcelamento e desconto PIX. O README registra que a curadoria foi manual (a extração automática troca os horários) e que RAG seria o próximo passo se o manual crescesse. |
| D4 | Modelo | **Gemini no free tier do Google AI Studio** (revisado pelo Diego em 2026-11-01: nenhuma API paga). Detalhes na seção D4 abaixo. |
| D5 | Interface | CLI: REPL + modo `--mensagem`. Histórico em memória com janela de N turnos. Transcripts `.md` opcionais. |
| D6 | Guardrails | Prompt (persona do §7, escopo, acessórios) + regras críticas no código: identificação do cliente, resposta genérica em falha, contato mascarado, nenhuma ferramenta de escrita, `REFERENCE_DATE` e escalonamento para humano. |
| D7 | Avaliação | pytest. Camada 1: testes unitários das ferramentas, sem LLM. Camada 2: **12 a 15 cenários e2e** cobrindo cada ferramenta, políticas, fora do escopo, identificação do cliente e prompt injection. **Vazamento de PII = 0 é gate de entrega.** Sem LLM-as-judge por enquanto. |

### D4 — Modelo e provedor (revisada)

- **Provedor padrão:** Gemini, `EMPORIO_PROVEDOR=gemini`.
- **Modelo padrão (revisado em 2026-11-02):** `gemini-3.5-flash-lite`. O `gemini-3.8-flash` fica só como alternativa documentada: no teste de 2026-11-01 ele ficou **indisponível no free tier**, com 503 em ~3 s (sobrecarga) e 504 em ~60 s (prazo) nas 12 chamadas do roteiro. O Flash-Lite rodou as 12 conversas sem 400 e sem 429. **Latência observada:** de 7 a 52 s por turno. O modelo pode ser trocado em `EMPORIO_MODELO`; se ficar vazio, vale o padrão do provedor.
- **SDK:** `google-genai` 2.31.0, publicada em 2026-10-14. É a versão estável mais recente com pelo menos 2 semanas de lançamento (fonte: https://pypi.org/project/google-genai/#history).
- **Por que o free tier:** custo zero para o Diego e para o avaliador, que só precisa criar uma chave gratuita no AI Studio (https://aistudio.google.com/apikey).
- **Fontes oficiais** (acessadas em 2026-11-01, verificação do AI Engineer):
  - **Preço:** https://ai.google.dev/gemini-api/docs/pricing. Para o Gemini 3.8 Flash, a coluna Free Tier traz input e output "Free of charge". O `gemini-3.5-flash-lite` também é "Free of charge".
  - **Modelo:** https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash. O modelo é Stable, e a página diz "Function calling: Supported".
  - **Cartão:** nem https://ai.google.dev/gemini-api/docs/api-key nem https://ai.google.dev/gemini-api/docs/billing exigem cartão para o free tier (inferido pela ausência da exigência).
  - **Região e idade:** https://ai.google.dev/gemini-api/docs/available-regions lista o Brasil. Os termos exigem 18 anos ou mais.
- **Limites de uso:** a documentação oficial (https://ai.google.dev/gemini-api/docs/rate-limits) não publica RPM, TPM nem RPD do free tier; manda consultar https://aistudio.google.com/rate-limit, logado. Os limites valem por projeto, e a cota diária reinicia à meia-noite do horário do Pacífico. **Os números da conta do Diego não foram verificados.** O adaptador trata o 429 com até 4 tentativas e espera exponencial com jitter, respeitando o `retryDelay`. Com a cota esgotada, o agente mostra uma mensagem própria ("limite de uso atingido") e os contatos humanos.
- **Uso dos dados no free tier:** pelos Gemini API Additional Terms (https://ai.google.dev/gemini-api/terms), nos serviços gratuitos "Google uses the content you submit to the Services and any generated responses to provide, improve, and develop Google products", e "human reviewers may read, annotate, and process your API input and output". Isso é aceitável aqui porque todos os dados são fictícios. Em produção, com clientes reais, seria preciso usar o Paid Tier (que não usa os dados para treino) ou outro provedor com DPA, por causa da LGPD.
- **Adaptador Anthropic:** continua no código (`EMPORIO_PROVEDOR=anthropic`, modelo padrão `claude-haiku-5-5`) com testes simulados, mas **NÃO foi validado com chamadas reais**, porque o Diego optou por não usar API paga.

## Dados

| # | Tema | Decisão |
|---|---|---|
| DD1 | Data de referência | `REFERENCE_DATE=2026-03-31` no `.env` (configurável), documentada no README. |
| DD2 | Promoções | Só `is_active=1` vale. Com duas ativas no mesmo produto, aplica-se o maior desconto. PIX não se soma à promoção. **O agente nunca promete desconto que não esteja ativo no CSV**, mesmo que o PDF fale de Black Friday. |
| DD3 | Arrependimento | O agente pergunta a data de recebimento e o canal (online ou loja). Na dúvida, encaminha para humano. |
| DD4 | Contatos | Telefone (67) 3341-4444, WhatsApp (67) 3321-4500 (§7), e-mail `contato@emporiodamusica.com.br` (sem acento). |
| DD5 | Parcelamento | Vale o §3.1: até 3x com parcela mínima de R$50; 4–6x com mínima de R$80; 7–12x com mínima de R$100. |
| DD6 | Defeito entre 31 e 90 dias | O agente informa as duas regras (§4.2 e §8.1) e encaminha para humano. |
| DD7 | Identificação | `order_id` + telefone **ou** e-mail do titular, com match exato na ferramenta. |
| DD8 | Totais divergentes | Usar `orders.total_brl` como valor pago, sem comentar a divergência com o cliente. A divergência dos pedidos 3 e 20 é citada na tabela de problemas do README. *(Confirmado pelo Diego.)* |
| DD9 | Disponibilidade | Disponível = `status=active` e `stock_quantity>0`. O produto 130 (`coming_soon`) aparece como "em breve". *(Confirmado pelo Diego.)* |
| DD10 | Provedor padrão | Claude Haiku 5.5 (ver D4). |

## Implementação (decisões de 2026-11-01)

| # | Tema | Decisão |
|---|---|---|
| I1 | `politicas.md` | Fica dentro do pacote (`src/emporio_agente/politicas.md`), distribuído como package data. |
| I2 | `.env` | `config.py` lê o `.env` (python-dotenv). Os testes e2e continuam pulados sem `ANTHROPIC_API_KEY`, para o avaliador rodar os unitários sem custo. |
| I3 | Busca de produto | Tolerante a maiúsculas, acentos, espaços e variações de nome ("takamine gd 20" encontra o Takamine GD20). Com mais de um resultado provável, o agente pergunta qual o cliente quer. Coberto por teste. |
| I4 | Preços | Calculados com `Decimal` e sempre formatados em reais no padrão brasileiro (`R$ 1.234,56`). Coberto por teste. |
| I5 | Erros das ferramentas | Produto ou pedido não encontrado e identificação que não confere retornam mensagens estruturadas, nunca exceções cruas para o modelo. Coberto por teste. |
| I6 | PII | Teste específico garante que nenhuma ferramenta devolve dados pessoais completos (e-mail, telefone, endereço) sem identificação válida. |
| I7 | Ordem e ponto de controle | Ordem: config → dados → ferramentas → `politicas.md` → provedor Anthropic → agente → CLI → e2e. **Parada obrigatória depois da CLI e antes dos e2e:** o Diego conversa com o agente para avaliar persona, escopo e comportamento. |
| I8 | README | Completado no final. |

## Detalhes técnicos da implementação (propostos pelo Python, aceitos pelo Orchestrator)

São escolhas de implementação sem impacto de arquitetura, registradas para transparência. O Diego pode revisar qualquer uma.

| # | Tema | Escolha |
|---|---|---|
| T1 | Ambiguidade da busca | `ambiguo: true` quando o texto casa pelo nome com 2 a 5 produtos disponíveis. Com 6 ou mais, volta uma lista ampla (até 10) com aviso para refinar. |
| T2 | Filtro de preço | `preco_min`/`preco_max` comparam com o **preço final**: o promocional quando há promoção ativa (DD2), ou o de tabela quando não há. A resposta mostra os dois valores. *(Revisado pelo Diego no ponto de controle; antes comparava com o preço de tabela.)* |
| T3 | Nada disponível | Com `so_disponiveis=true` e nenhum disponível, a ferramenta devolve `produtos_indisponiveis` com rótulo, para o agente não negar um item que existe (ex.: o 96, esgotado). |
| T4 | Parcelamento | O pagamento em 1x nunca é bloqueado. Os mínimos valem de 2x em diante. Parcela abaixo do mínimo volta com `permitido: false`, o motivo e o máximo de parcelas permitido. Mais de 12x é argumento inválido. |
| T5 | `calcular_pagamento` | Um valor livre é tratado como preço de tabela. Com `product_id`, usa o preço promocional se houver promoção ativa, e o PIX não se soma. |
| T6 | Status do pedido | Rótulos: Pendente, Confirmado, Enviado, Entregue, Cancelado. Datas em dd/mm/aaaa. |
| T7 | Contato do titular | `consultar_pedido` devolve telefone e e-mail mascarados. |
| T8 | Itens do pedido | Mostra o nome atual do catálogo, sem preço por item (`order_items` não tem preço). |
| T9 | Chave de API | Vem do `Config`, que lê o `.env` sem alterar `os.environ`. Sem chave, o provedor levanta `ProvedorErro`. |
| T10 | Data nas ferramentas | ~~Nenhuma ferramenta usa a data de referência.~~ *(Revisada em 2026-11-02: só `consultar_pedido` usa, para `previsao_vencida`, ver T24.)* Os prazos de troca ficam no prompt e nas políticas. |
| T11 | Hora do dia | ~~O agente só conhece a data, não a hora.~~ *(Substituída pela T23 em 2026-11-02: o modelo ignorou a regra e afirmou "estamos abertos" sem saber a hora.)* |
| T12 | System prompt no provedor | O agente envia o prompt inteiro como uma string (`montar_system_prompt`) com `cache_control`. A variante em blocos estável/variável do `politicas.py` não é usada: com `REFERENCE_DATE` fixa, o cache funciona igual. |
| T13 | Turno com falha | Um turno que falha por erro técnico (ProvedorErro, resposta vazia ou cortada no meio de uma ferramenta) **não entra no histórico**, e o cliente pode repetir. O fallback por limite de iterações e a resposta cortada com texto entram só como o par cliente/assistente, sem as idas e vindas de ferramenta. |
| T14 | Sinal de falha | `RespostaAgente.falhou` indica uma resposta de fallback. A CLI com `--mensagem` sai com código 1 quando `falhou=True`, e com 0 caso contrário. |
| T15 | Dados pessoais nos registros locais | `--mostrar-ferramentas` e os transcripts mostram os argumentos exatos, inclusive o telefone ou e-mail digitado para identificar o pedido. É uma ferramenta de avaliação local e `transcripts/` está no `.gitignore`. As conversas de exemplo publicadas são revisadas antes do commit. |
| T16 | Tamanho da resposta | `max_tokens` fixo em 1024 por chamada, sem variável de ambiente. |
| T17 | Rótulos da CLI | "Você:" e "Atendente:", neutros. A persona vem só do prompt. |
| T18 | Ctrl+C | Ctrl+C no meio de uma resposta encerra a sessão, não só cancela o turno. |
| T19 | Gemini: API do SDK | `client.models.generate_content` com chamada automática de funções desligada (o loop é nosso, D1). A Interactions API, mais nova, não foi usada porque não segue o contrato de mensagens atual. |
| T20 | Gemini: raciocínio | `max_output_tokens = max_tokens + 2048` (`MARGEM_RACIOCINIO`), porque no Gemini 3 os tokens de raciocínio contam no limite. `thinking_level` não foi configurado. O adaptador devolve a `thought_signature` de cada chamada no histórico, como o Gemini 3 exige. |
| T21 | Gemini: erros transitórios | 429 e 5xx são repetidos com espera exponencial (até 4 tentativas, timeout de 60s por requisição). Só o 429 vira `COTA_ESGOTADA`, e um 5xx persistente vira erro técnico genérico. No pior caso, um turno pode demorar alguns minutos com o serviço instável. |
| T22 | Testes herméticos | O `conftest` não carrega mais o `.env` em `os.environ`, e as variáveis do shell são limpas nos testes unitários. Os e2e leem o `.env` via `Config` e são pulados se faltar a chave do provedor configurado. |
| T23 | Hora e loja aberta/fechada (opção B) | O modelo não tem relógio, então **o código calcula** "aberta ou fechada agora" (`horario.py`, §2, fuso America/Campo_Grande) e entrega o fato pronto no prompt. O relógio padrão usa a **data de referência** (`REFERENCE_DATE`, DD1) com a **hora do relógio real** no fuso de Campo Grande, para dia da semana e hora ficarem coerentes com o "hoje" dos pedidos e das promoções. `EMPORIO_AGORA` (AAAA-MM-DDTHH:MM, opcional, no fuso de Campo Grande; inválida gera `ConfigError`) fixa o instante em testes e demonstrações. O `Agente` recebe um relógio (callable) e remonta **só a parte variável** do prompt a cada turno; a parte estável (cache) não muda. O prompt injetado (testes) não é remontado. A frase "Você não sabe a hora atual..." foi trocada pela regra "nunca afirme que a loja está aberta ou fechada além do fato informado". O cálculo usa só o horário semanal e não conhece feriados (o prompt avisa). `tzdata` entra nas dependências, porque o Windows não traz o banco de fusos. |
| T24 | `previsao_vencida` (caso 6) | `consultar_pedido` devolve `previsao_vencida: true` e `orientacao_previsao` quando a previsão de entrega é **anterior** à data de referência e o status não é `delivered` nem `cancelled` (no próprio dia ainda não vence). `Ferramentas` recebe a data de referência como parâmetro opcional; `criar_agente` passa `config.reference_date`. Regra no prompt: informar o status exatamente como a ferramenta retornar, sem deduzir entrega. Teste com o pedido 8 (enviado, previsão 28/02/2026, referência 2026-03-31). Motivo: no roteiro real o agente inventou "pedido já entregue". |
| T25 | Ordenação por preço (caso 1) | Com `preco_min` ou `preco_max`, `buscar_produtos` ordena pelo **preço final** crescente (desempate por `product_id`). A resposta traz `total` (todos os que casam) e `nao_exibidos` (`total` menos os mostrados), e o aviso manda informar o cliente quando há mais. Sem filtro de preço a ordem não muda. Motivo: no roteiro real a busca cortava em 10 por ordem de id e deixava um item mais barato de fora. |
| T26 | Regra de promoção (caso 7) | Qualquer pergunta sobre promoção, desconto ou Black Friday chama `listar_promocoes_ativas` **antes** de responder (regra no prompt e na descrição da ferramenta). O agente pode citar o que as políticas dizem de datas comemorativas (§6.1), mas nunca promete desconto inativo (DD2). Motivo: "tem promoções ativas" foi afirmado sem chamar a ferramenta. |
| T27 | Pergunta 8 ("palheta") | O critério do Diego foi **aceito como cumprido pela política, sem ferramenta**: a loja não vende acessórios (§1), e responder por política é correto. A resposta não precisa de chamada de ferramenta. |
| T28 | PIX: uma única função de preço | `preco_pix` em `ferramentas.py` é a única regra do PIX, usada por `buscar_produtos` e `detalhar_produto` (via `_visao`) e por `calcular_pagamento`. Desconto = `arredondar(preço aplicável × 5%)` em centavos, `ROUND_HALF_UP`; preço PIX = preço aplicável − desconto (579,90 → desconto 29,00 → PIX 550,90). O preço aplicável é o de tabela: o PIX não soma com promoção. **Revoga a divergência 550,90 × 550,91**: a busca/detalhe arredondava o preço final (579,90 × 0,95 = 550,905 → 550,91) e o cálculo arredondava o desconto. Teste parametrizado sobre todos os produtos do CSV garante o mesmo valor nas três ferramentas. |
| T29 | Regras de prompt (rodada final) | (a) Não mencionar descontos ou datas de campanhas futuras (ex.: "Black Friday em novembro"): se a campanha não está na ferramenta, dizer só que não há promoção dessa campanha ativa e listar o que a ferramenta devolveu. (b) Em defeito/garantia, citar os prazos em números: troca por defeito até 30 dias da compra (§4.2) e garantia legal de 90 dias a partir do recebimento (§8.1). Os prazos também estão resumidos em `politicas.md`, com as seções de origem (conferidas no texto curado, que já os trazia). |

## Processo

- Repositório público: https://github.com/DiegoLCirqueira/emporio-agente. Push ao fim de cada etapa concluída, nunca force push.
- O README deve ter a seção "Tratamento e qualidade dos dados", resumindo `docs/exploracao-dados.md` e como cada problema foi tratado.
