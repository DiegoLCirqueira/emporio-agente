import pytest

from emporio_agente.config import DADOS_DIR_PADRAO
from emporio_agente.dados import carregar_dados
from emporio_agente.ferramentas import Ferramentas, formatar_brl


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


# --- PIX: uma única função de preço (T28) --------------------------------------------------

from decimal import Decimal  # noqa: E402

from emporio_agente.config import DADOS_DIR_PADRAO as _DIR  # noqa: E402
from emporio_agente.ferramentas import preco_pix  # noqa: E402

_PRODUTOS = carregar_dados(_DIR).produtos


@pytest.mark.parametrize(
    "preco, desconto, final",
    [
        ("579.90", "29.00", "550.90"),  # 28,995 sobe para 29,00 (ROUND_HALF_UP)
        ("2199.00", "109.95", "2089.05"),
        ("1000.00", "50.00", "950.00"),
    ],
)
def test_preco_pix_arredonda_o_desconto_e_subtrai(preco, desconto, final):
    assert preco_pix(Decimal(preco)) == (Decimal(desconto), Decimal(final))


@pytest.mark.parametrize("produto", _PRODUTOS, ids=lambda p: str(p.product_id))
def test_todas_as_ferramentas_dao_o_mesmo_preco_pix(ferr, produto):
    pid = produto.product_id
    calc_pix = calc(ferr, forma="pix", product_id=pid)
    detalhe = ferr.executar("detalhar_produto", {"product_id": pid})["produto"]
    busca = ferr.executar("buscar_produtos", {"texto": produto.nome, "so_disponiveis": False})
    visoes = [p for p in busca.get("produtos", []) + busca.get("candidatos", []) if p["product_id"] == pid]
    assert visoes, "produto não apareceu na busca pelo próprio nome"
    if "preco_promocional" in detalhe:  # PIX não soma com promoção
        assert "preco_pix" not in detalhe and all("preco_pix" not in v for v in visoes)
        assert calc_pix["valor_final"] == detalhe["preco_promocional"]
        return
    esperado = formatar_brl(preco_pix(produto.preco)[1])
    assert detalhe["preco_pix"] == esperado
    assert all(v["preco_pix"] == esperado for v in visoes)
    assert calc_pix["valor_final"] == esperado
    assert calc_pix["desconto_pix"] == formatar_brl(preco_pix(produto.preco)[0])
