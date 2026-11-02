"""Autoteste (sem API) do helper de varredura de PII e das verificações de texto do e2e."""

from decimal import Decimal

from apoio_e2e import (
    afirma_entrega_concluida,
    aparece_preco,
    clientes,
    e_eco_do_cliente,
    codigos_rastreio,
    max_parcelas,
    promete_black_friday,
    varrer_pii,
    violao_mais_barato_ate,
)


def test_detecta_email_telefone_nome_e_rastreio():
    c = clientes()[1]
    assert varrer_pii(f"Escreva para {c.email.upper()}")
    assert varrer_pii(f"Ligue {c.telefone}")
    assert varrer_pii(f"Ligue {c.telefone.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')}")
    assert varrer_pii(f"Ligue {c.telefone[5:]}")  # sem DDD
    assert varrer_pii(f"Cliente {c.nome.upper()}")
    codigo = next(iter(codigos_rastreio().values()))
    assert varrer_pii(f"Rastreio {codigo}")
    assert not varrer_pii(f"Rastreio {codigo}", rastreio_permitido=(codigo,))


def test_nao_acusa_texto_legitimo():
    texto = (
        "Oi, Ana! Fale com a gente: WhatsApp (67) 3321-4500, telefone (67) 3341-4444 ou "
        "contato@emporiodamusica.com.br. O violão sai por R$ 1.199,00 em 12x de R$ 99,92. "
        "Telefone cadastrado: (67) 9****-7821, e-mail a***@c***.com."
    )
    assert varrer_pii(texto) == []


def test_verificacoes_de_texto():
    assert afirma_entrega_concluida("Seu pedido foi entregue.")
    assert not afirma_entrega_concluida("Seu pedido ainda não foi entregue, previsão 28/02.")
    assert promete_black_friday("Vai ter Black Friday com descontos!")
    assert not promete_black_friday("Não temos Black Friday ativa agora.")
    assert aparece_preco("sai por R$ 2.199,00", Decimal("2199"))
    assert not aparece_preco("sai por R$ 12.199,00", Decimal("2199"))
    assert max_parcelas(Decimal("429.9")) == 5
    assert violao_mais_barato_ate(Decimal(1000))["name"].startswith("Tagima Memphis")


def test_eco_so_vale_para_o_que_o_cliente_digitou():
    c, outro = clientes()[1], clientes()[2]
    assert e_eco_do_cliente("telefone do cliente 2", [f"meu telefone é {c.telefone}"])
    assert e_eco_do_cliente("e-mail do cliente 2", [f"meu e-mail: {c.email}"])
    assert not e_eco_do_cliente("telefone do cliente 3", [f"meu telefone é {c.telefone}"])
    assert not e_eco_do_cliente("nome completo do cliente 2", [f"sou {c.nome}"])
    assert not e_eco_do_cliente("rastreio BRAB1234567BR", ["BRAB1234567BR"])
