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
- **Modelo padrão:** `gemini-3.8-flash`. Alternativa documentada: `gemini-3.5-flash-lite`. O modelo pode ser trocado em `EMPORIO_MODELO`; se ficar vazio, vale o padrão do provedor.
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
| T10 | Data nas ferramentas | Nenhuma ferramenta usa a data de referência. Os prazos ficam no prompt e nas políticas. |
| T11 | Hora do dia | O agente só conhece a data, não a hora. Ele não afirma se a loja está aberta agora: informa o horário do dia. (Correção do Orchestrator no prompt.) |
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

## Processo

- Repositório público: https://github.com/DiegoLCirqueira/emporio-agente. Push ao fim de cada etapa concluída, nunca force push.
- O README deve ter a seção "Tratamento e qualidade dos dados", resumindo `docs/exploracao-dados.md` e como cada problema foi tratado.
