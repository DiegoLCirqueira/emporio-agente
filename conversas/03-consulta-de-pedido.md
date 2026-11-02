# Conversa 3: consulta de pedido (identificação válida e inválida)

- Modelo: `gemini-3.5-flash-lite`
- Provedor: gemini
- Data de execução: 2026-11-02
- Data de referência ("hoje" do sistema): 2026-03-31
- Execução real via `criar_agente`; respostas do agente sem edição (telefones e e-mails de pessoas aparecem mascarados).
- Ordem dos casos nesta conversa: identificação **inválida → válida** (telefone inexistente primeiro, depois o telefone correto do titular).
- Nota: testado também na ordem válida→inválida: nesse caso o modelo respondeu 'não foi possível localizar' sem rechamar `consultar_pedido` (comportamento registrado nas limitações do README).

## Turno 1

**Cliente:** Oi! Queria saber do meu pedido 8. Acho que meu telefone cadastrado é (67) 9****-0000

**Ferramentas chamadas:**
- `consultar_pedido`: erro (PEDIDO_OU_IDENTIFICACAO_INVALIDOS)

**Atendente:** Não foi possível localizar o pedido com os dados informados. Por favor, confira o número do pedido e o telefone ou e-mail cadastrado e tente novamente.

## Turno 2

**Cliente:** Ops, errei o número. O certo é (67) 9****-7821.

**Ferramentas chamadas:**
- `consultar_pedido`: ok

**Atendente:** Ana, o status do seu pedido 8 (Kala KA-C Concert Mogno) é **Enviado**.

A previsão de entrega era para 28/02/2026, ou seja, a previsão informada já passou e o status continua o registrado. Se preferir, posso encaminhar o seu caso para a nossa equipe humana verificar os detalhes do envio com a transportadora. O que acha?
