# Desafio Técnico — AI Engineer (Artefact)

> Texto extraído de `docs/desafio_tecnico_ai_eng_artefact.pdf` (o PDF original fica versionado ao lado). A formatação foi adaptada para Markdown e o conteúdo não foi alterado.

Seja bem-vindo(a) à primeira fase do processo seletivo para AI Engineer na Artefact.
Queremos entender como você pensa e estrutura soluções envolvendo LLMs e integrações com ferramentas externas.

Avaliaremos sua lógica, clareza e iniciativa. Estamos mais interessados em como você resolve o problema e toma decisões do que em uma solução perfeita.

## Cenário

A Empório da Música é uma loja fictícia de instrumentos musicais localizada em Campo Grande/MS. Hoje, o atendimento é inteiramente realizado pela equipe, que está sobrecarregada com perguntas recorrentes: horários de funcionamento, status de pedido, preço e disponibilidade de produtos, etc.

Sua missão: prototipar um agente de atendimento que irá auxiliar a equipe no atendimento. Para isso, a loja forneceu os seguintes materiais para uso do agente:

| Arquivo | Conteúdo |
|---|---|
| `data/*.csv` | Tabelas com dados da operação, como produtos, pedidos, clientes e promoções |
| `data/políticas_da_loja.pdf` | Manual interno de políticas e procedimentos de atendimento ao cliente. |

> Atenção: você não é obrigado a utilizar todos os dados, use o que considerar necessário para a melhor experiência de atendimento ao cliente.

## O que você precisa construir

Um projeto em Python do agente de mensagens de texto que atenda clientes da Empório da Música. O agente deve:

- Assumir uma persona alinhada com a identidade e o tom da loja.
- Receber e responder mensagens com base no contexto disponibilizado.
- Saber quando consultar dados (ex.: disponibilidade, preços, status de pedido) e quando consultar políticas (ex.: regras de troca, horários, formas de pagamento).
- Lidar adequadamente com perguntas que fujam do escopo da loja.

## Decisões Técnicas

As escolhas abaixo ficam a seu critério, mas devem ser justificadas no README. Não há resposta certa, queremos entender seu raciocínio.

| Decisão | Orientações |
|---|---|
| Framework(s) / abordagem do agente | RAG, function calling, ReAct, agente de SQL, híbrido, etc. |
| Modelo e Provedor | Você pode escolher modelos pagos ou grátis, locais ou via API. |
| Interface de interação | CLI, notebook, API, ou UI simples — o foco é o agente funcionando corretamente. |
| Persistência do histórico de conversa | Implemente se fizer sentido para a experiência do usuário. |
| Tratamento dos dados | Faça o tratamento de dados que julgar necessário. |

> Única restrição técnica obrigatória: uso de Python como linguagem principal.

## Entregáveis

### 1. Repositório Git Público

Link para o repositório público do seu projeto no GitHub. Mantenha um histórico de commits com progresso real — não faça force-push de tudo em um único commit. Não altere nada no repositório após a data e horário de entrega.

### 2. README.md

- Todas as instruções necessárias para rodar o projeto: configuração de ambiente, provedor do modelo, comandos, etc.
- Justificativa das decisões técnicas: framework, LLM, arquitetura de retrieval, estratégia de prompt, etc.
- Limitações conhecidas: e o que você faria com mais tempo.
- Uso de assistentes de código: caso faça uso de algum recurso de IA (Copilot, Claude, Cursor, etc.), explique qual a escolhida e como utilizou. Queremos entender o seu workflow. A depender de como a ferramenta tenha sido explorada, isso pode ser visto como um ponto positivo e não irá prejudicar a sua avaliação.

### 3. Exemplos de interação com o agente

Inclua no repositório entre 3 e 5 conversas em formato .md ou .txt, ou arquivo de imagem, cobrindo cenários variados. Ao menos uma delas deve demonstrar o agente lidando com uma situação não trivial — consultando dados em tempo real ou aplicando regras das políticas. Sugestões de possíveis cenários:

- "Quais opções de violões disponíveis custando até R$1000?" — consulta sobre o catálogo de produtos
- "Qual o endereço da loja?" — informações gerais da loja
- "Quanto custa o Takamine GD20?" — consulta de preço
- "Me arrependi da minha compra, posso devolver meu pedido?" — aplicação das políticas de devolução

## Como Entregar

Responda o e-mail em que você recebeu este arquivo com:

- O link do repositório público contendo os itens indicados na seção anterior.

> Atenção ao prazo: respeite a data de entrega informada no e-mail do processo seletivo.

## Dúvidas?

Se algo no enunciado estiver ambíguo, ou encontrar alguma outra dificuldade, assuma uma interpretação razoável, documente a suposição no README e siga em frente.
Queremos entender como você lida com situações em que nem todas as informações estão disponíveis, então não tenha receio de tomar decisões justificadas ao longo do caminho.
