from datetime import date
from decimal import Decimal

import pytest

from emporio_agente import dados as modulo_dados
from emporio_agente.config import DADOS_DIR_PADRAO
from emporio_agente.dados import Dados, carregar_dados


@pytest.fixture(scope="module")
def dados() -> Dados:
    return carregar_dados(DADOS_DIR_PADRAO)


def test_volumes(dados):
    assert len(dados.produtos) == 65
    assert len(dados.categorias) == 9
    assert len(dados.pedidos) == 20
    assert len(dados.promocoes) == 25


def test_produtos_ordenados_por_id(dados):
    ids = [p.product_id for p in dados.produtos]
    assert ids == sorted(ids)
    assert ids[0] == 81 and ids[-1] == 145


def test_precos_sao_decimal_exatos(dados):
    p = dados.produto(95)
    assert p.preco == Decimal("2199")
    assert dados.produto(81).preco == Decimal("599.9")
    assert isinstance(dados.pedido(4).total, Decimal)
    assert dados.pedido(4).total == Decimal("799.9")


def test_specs_sao_dict_e_ids_int(dados):
    p = dados.produto(81)
    assert p.specs["top"] == "Spruce"
    assert isinstance(p.product_id, int) and isinstance(p.category_id, int)
    assert isinstance(p.estoque, int)
    assert p.created_at == date(2021, 3, 15)


def test_produto_inexistente_devolve_none(dados):
    assert dados.produto(9999) is None


def test_itens_do_pedido(dados):
    itens = dados.itens_do_pedido(15)
    assert {(i.product_id, i.quantidade) for i in itens} == {(82, 1), (106, 1)}


def test_pedido_tem_campos_opcionais_none_quando_vazios(dados):
    pendente = dados.pedido(13)
    assert pendente.tracking_code is None and pendente.estimated_delivery is None
    entregue = dados.pedido(1)
    assert entregue.tracking_code == "BRAB1234567BR"
    assert entregue.estimated_delivery == date(2025, 10, 25)
    assert dados.pedido(17).notes.startswith("Pedido cancelado")


def test_promocoes_tem_flag_booleana(dados):
    ativas = [p.promotion_id for p in dados.promocoes if p.ativa]
    assert ativas == [12, 14, 19, 24]


def test_titular_exige_identificacao_valida(dados):
    # pedido 1 é do cliente 3 (Pedro Henrique Oliveira)
    titular = dados.titular_do_pedido(1, telefone="(67) 98432-1098")
    assert titular is not None and titular.customer_id == 3
    assert dados.titular_do_pedido(1, email=" Pedro.Oliveira@JMAIL.com ") is not None
    assert dados.titular_do_pedido(1, telefone="67984321098") is not None


def test_titular_rejeita_identificacao_errada_ou_pedido_inexistente(dados):
    assert dados.titular_do_pedido(1, telefone="(67) 99812-3456") is None
    assert dados.titular_do_pedido(1, email="lucas.mendes@jmail.com") is None
    assert dados.titular_do_pedido(999, telefone="(67) 98432-1098") is None
    assert dados.titular_do_pedido(1) is None
    assert dados.titular_do_pedido(1, telefone="", email="") is None


def test_nenhuma_api_publica_lista_ou_busca_clientes(dados):
    publicos = [n for n in dir(dados) if not n.startswith("_")]
    assert not [n for n in publicos if "cliente" in n.lower() and n != "titular_do_pedido"]
    assert not hasattr(modulo_dados, "clientes")
    with pytest.raises(AttributeError):
        dados.clientes  # noqa: B018


def test_carregar_dados_com_diretorio_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        carregar_dados(tmp_path)
