import pytest

from emporio_agente.config import DADOS_DIR_PADRAO
from emporio_agente.dados import carregar_dados
from emporio_agente.ferramentas import Ferramentas


@pytest.fixture(scope="module")
def ferr() -> Ferramentas:
    return Ferramentas(carregar_dados(DADOS_DIR_PADRAO))


def calc(ferr, **args):
    return ferr.executar("calcular_pagamento", args)


def codigo_erro(r):
    assert r["ok"] is False
    return r["erro"]["codigo"]


# --- PIX -------------------------------------------------------------------------------


def test_pix_sobre_valor_informado(ferr):
    r = calc(ferr, valor=1000, forma="pix")
    assert r["ok"] and r["valor_final"] == "R$ 950,00" and r["desconto_pix"] == "R$ 50,00"


def test_pix_sobre_produto_sem_promocao(ferr):
    r = calc(ferr, product_id=95, forma="pix")
    assert r["valor_base"] == "R$ 2.199,00"
    assert r["valor_final"] == "R$ 2.089,05"
    assert r["produto"]["product_id"] == 95


def test_pix_nao_se_soma_a_promocao(ferr):
    r = calc(ferr, product_id=90, forma="pix")
    assert r["valor_base"] == "R$ 1.967,18"
    assert r["valor_final"] == "R$ 1.967,18"
    assert "desconto_pix" not in r
    assert any("PIX" in o for o in r["observacoes"])


# --- crédito e DD5 ---------------------------------------------------------------------


def test_credito_a_vista_e_padrao(ferr):
    r = calc(ferr, valor=30, forma="credito")
    assert r["ok"] and r["parcelas"] == 1 and r["permitido"] is True and r["valor_final"] == "R$ 30,00"


@pytest.mark.parametrize(
    "valor,parcelas,parcela,permitido",
    [
        (1000, 3, "R$ 333,33", True),
        (1000, 4, "R$ 250,00", True),
        (1000, 10, "R$ 100,00", True),  # exatamente o mínimo de R$ 100 vale
        (1000, 12, "R$ 83,33", False),
        (140, 3, "R$ 46,67", False),  # abaixo de R$ 50
        (100, 2, "R$ 50,00", True),
        (480, 6, "R$ 80,00", True),
        (470, 6, "R$ 78,33", False),
    ],
)
def test_regras_de_parcelamento(ferr, valor, parcelas, parcela, permitido):
    r = calc(ferr, valor=valor, forma="credito", parcelas=parcelas)
    assert r["ok"] is True
    assert r["valor_parcela"] == parcela
    assert r["permitido"] is permitido


def test_parcelamento_nao_permitido_sugere_maximo(ferr):
    r = calc(ferr, valor=1000, forma="credito", parcelas=12)
    assert r["permitido"] is False
    assert r["max_parcelas_permitidas"] == 10
    assert "R$ 100,00" in r["motivo"]
    r = calc(ferr, valor=140, forma="credito", parcelas=3)
    assert r["max_parcelas_permitidas"] == 2


def test_credito_em_produto_com_promocao_usa_preco_promocional(ferr):
    r = calc(ferr, product_id=127, forma="credito", parcelas=3)
    assert r["valor_base"] == "R$ 323,10"
    assert r["valor_parcela"] == "R$ 107,70"
    assert r["permitido"] is True


def test_mais_de_12x_e_invalido(ferr):
    assert codigo_erro(calc(ferr, valor=5000, forma="credito", parcelas=13)) == "ARGUMENTO_INVALIDO"


def test_parcelas_menor_que_um_e_invalido(ferr):
    assert codigo_erro(calc(ferr, valor=5000, forma="credito", parcelas=0)) == "ARGUMENTO_INVALIDO"


# --- débito e boleto -------------------------------------------------------------------


@pytest.mark.parametrize("forma", ["debito", "boleto"])
def test_debito_e_boleto_sem_desconto_nem_parcelamento(ferr, forma):
    r = calc(ferr, valor=500, forma=forma)
    assert r["ok"] and r["valor_final"] == "R$ 500,00" and r["parcelas"] == 1
    assert codigo_erro(calc(ferr, valor=500, forma=forma, parcelas=2)) == "ARGUMENTO_INVALIDO"


@pytest.mark.parametrize("forma,esperado", [("Crédito", "credito"), ("PIX", "pix"), ("cartão de crédito", "credito")])
def test_forma_aceita_variacoes(ferr, forma, esperado):
    assert calc(ferr, valor=100, forma=forma)["forma"] == esperado


# --- validação -------------------------------------------------------------------------


def test_exige_valor_ou_produto_e_nunca_os_dois(ferr):
    assert codigo_erro(calc(ferr, forma="pix")) == "ARGUMENTO_INVALIDO"
    assert codigo_erro(calc(ferr, valor=100, product_id=95, forma="pix")) == "ARGUMENTO_INVALIDO"


@pytest.mark.parametrize("valor", [0, -10, "abc"])
def test_valor_invalido(ferr, valor):
    assert codigo_erro(calc(ferr, valor=valor, forma="pix")) == "ARGUMENTO_INVALIDO"


def test_forma_invalida_ou_ausente(ferr):
    assert codigo_erro(calc(ferr, valor=100, forma="cheque")) == "ARGUMENTO_INVALIDO"
    assert codigo_erro(calc(ferr, valor=100)) == "ARGUMENTO_INVALIDO"


def test_produto_inexistente(ferr):
    assert codigo_erro(calc(ferr, product_id=9999, forma="pix")) == "PRODUTO_NAO_ENCONTRADO"


def test_valor_em_formato_brasileiro(ferr):
    assert calc(ferr, valor="1.299,90", forma="boleto")["valor_final"] == "R$ 1.299,90"
