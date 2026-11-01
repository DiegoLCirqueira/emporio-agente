# Decisões tomadas

Decisões do Diego em 2026-11-01 sobre as opções de `docs/opcoes-arquitetura.md`. Este arquivo é a fonte de verdade para a implementação. Uma mudança aqui exige nova decisão do Diego.

## Arquitetura

| # | Tema | Decisão |
|---|---|---|
| D1 | Abordagem | Function calling com loop próprio sobre o SDK do provedor, sem LangChain/LangGraph. Máximo de 5 iterações de ferramenta por turno. |
| D2 | Dados | Ferramentas específicas por intenção sobre `csv` + `Decimal` em memória (stdlib), com as regras de negócio no código. Ferramentas: `buscar_produtos`, `detalhar_produto`, `consultar_pedido`, `listar_promocoes_ativas` e, opcionalmente, `calcular_pagamento`. Nenhuma ferramenta lista ou busca clientes. |
| D3 | Políticas | `politicas.md` curado à mão, inteiro no system prompt (com prompt caching), **sem RAG**. Cada trecho cita a seção do PDF de origem (ex.: "§4.1"). Testes automatizados confirmam os fatos críticos: horário de cada dia, prazos de troca, devolução e garantia, regras de parcelamento e desconto PIX. O README registra que a curadoria foi manual (a extração automática troca os horários) e que RAG seria o próximo passo se o manual crescesse. |
| D4 | Modelo | Claude Haiku 5.5 (`claude-haiku-5-5`). Interface de provedor fina desde já, com implementação **só do Anthropic**. O adaptador Gemini é bônus no fim do dia 2, só se houver folga. |
| D5 | Interface | CLI: REPL + modo `--mensagem`. Histórico em memória com janela de N turnos. Transcripts `.md` opcionais. |
| D6 | Guardrails | Prompt (persona do §7, escopo, acessórios) + regras críticas no código: identificação do cliente, resposta genérica em falha, contato mascarado, nenhuma ferramenta de escrita, `REFERENCE_DATE` e escalonamento para humano. |
| D7 | Avaliação | pytest. Camada 1: testes unitários das ferramentas, sem LLM. Camada 2: **12 a 15 cenários e2e** cobrindo cada ferramenta, políticas, fora do escopo, identificação do cliente e prompt injection. **Vazamento de PII = 0 é gate de entrega.** Sem LLM-as-judge por enquanto. |

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

## Processo

- Repositório público: https://github.com/DiegoLCirqueira/emporio-agente. Push ao fim de cada etapa concluída, nunca force push.
- O README deve ter a seção "Tratamento e qualidade dos dados", resumindo `docs/exploracao-dados.md` e como cada problema foi tratado.
