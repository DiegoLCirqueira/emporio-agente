import shutil
from decimal import Decimal

import pytest

from emporio_agente.config import DADOS_DIR_PADRAO
from emporio_agente.dados import carregar_dados
from emporio_agente.ferramentas import Ferramentas, formatar_brl, normalizar


@pytest.fixture(scope="module")
def ferr() -> Ferramentas:
    return Ferramentas(carregar_dados(DADOS_DIR_PADRAO))


def ids(resp, chave="produtos"):
    return [p["product_id"] for p in resp.get(chave, [])]


# --- formatação e normalização ---------------------------------------------------------


@pytest.mark.parametrize(
    "valor,esperado",
    [
        (Decimal("1967.18"), "R$ 1.967,18"),
        (Decimal("799.9"), "R$ 799,90"),
        (Decimal("0"), "R$ 0,00"),
        (Decimal("1234567.5"), "R$ 1.234.567,50"),
        (Decimal("19567"), "R$ 19.567,00"),
    ],
)
def test_formatar_brl(valor, esperado):
    assert formatar_brl(valor) == esperado


def test_normalizar():
    assert normalizar("  Violão   TAKAMINE-GD20 ") == "violao takamine gd20"


# --- buscar_produtos (I3) --------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    ["takamine gd 20", "Takamine GD20", "TAKAMINE-GD-20", "  takamine   gd20  ", "takamíne gd 20"],
)
def test_busca_tolerante_a_formato(ferr, texto):
    r = ferr.executar("buscar_produtos", {"texto": texto})
    assert r["ok"] is True
    assert ids(r) == [95]
    assert r["ambiguo"] is False


def test_violao_sem_acento_casa_com_categoria(ferr):
    r = ferr.executar("buscar_produtos", {"texto": "violao"})
    assert r["ok"] and r["produtos"]
    assert {p["categoria"] for p in r["produtos"]} == {"Violões"}
    r2 = ferr.executar("buscar_produtos", {"categoria": "violao"})
    assert {p["categoria"] for p in r2["produtos"]} == {"Violões"}


def test_busca_com_erro_de_digitacao_usa_fallback(ferr):
    r = ferr.executar("buscar_produtos", {"texto": "tagma dalas"})
    assert 86 in ids(r)  # Tagima Dallas Tuner Aço Natural


def test_ambiguidade_vem_explicita(ferr):
    r = ferr.executar("buscar_produtos", {"texto": "bass"})
    assert r["ambiguo"] is True
    assert {135, 137, 138} <= set(ids(r, "candidatos"))
    assert r["produtos"] == []
    assert "pergunte" in r["instrucao"].lower()


def test_resultado_unico_nao_e_ambiguo(ferr):
    r = ferr.executar("buscar_produtos", {"texto": "martin d28"})
    assert ids(r) == [93]
    assert r["ambiguo"] is False


def test_token_exato_vence_prefixo(ferr):
    # "d28" não deve trazer também o D-28E (108)
    assert ids(ferr.executar("buscar_produtos", {"texto": "martin d28"})) == [93]
    # mas "d28e" encontra o 108
    assert ids(ferr.executar("buscar_produtos", {"texto": "martin d28e"})) == [108]


def test_busca_ampla_nao_e_ambiguidade(ferr):
    r = ferr.executar("buscar_produtos", {"texto": "yamaha"})
    assert r["ambiguo"] is False
    assert len(r["produtos"]) >= 5


def test_sete_cordas_e_produto_nao_acessorio(ferr):
    r = ferr.executar("buscar_produtos", {"texto": "7 cordas"})
    achados = set(ids(r)) | set(ids(r, "candidatos"))
    assert {109, 110, 111, 112} <= achados
    assert r.get("possivel_acessorio") is not True


@pytest.mark.parametrize("texto", ["cordas de violão", "palheta", "capa para guitarra", "cabo P10"])
def test_acessorio_nao_casa_com_nome_de_produto(ferr, texto):
    r = ferr.executar("buscar_produtos", {"texto": texto})
    assert r["ok"] is True
    assert r["produtos"] == []
    assert r["possivel_acessorio"] is True


def test_categoria_sem_produtos(ferr):
    r = ferr.executar("buscar_produtos", {"categoria": "Cordas Orquestrais"})
    assert r["ok"] and r["produtos"] == []
    assert "aviso" in r


def test_filtro_de_preco(ferr):
    r = ferr.executar("buscar_produtos", {"categoria": "ukulele", "preco_max": 200})
    assert set(ids(r)) == {116, 118, 119}
    r = ferr.executar("buscar_produtos", {"categoria": "ukulele", "preco_min": "1.500,00"})
    assert set(ids(r)) == {126, 129}


def test_so_disponiveis_esconde_esgotado_mas_informa(ferr):
    r = ferr.executar("buscar_produtos", {"texto": "giannini gf-3d"})
    assert r["produtos"] == []
    esgotado = r["produtos_indisponiveis"][0]
    assert esgotado["product_id"] == 96
    assert esgotado["disponibilidade"]["codigo"] == "esgotado"
    r = ferr.executar("buscar_produtos", {"texto": "giannini gf-3d", "so_disponiveis": False})
    assert ids(r) == [96]


def test_resultados_limitados_com_total(ferr):
    r = ferr.executar("buscar_produtos", {"categoria": "violoes"})
    assert len(r["produtos"]) <= 10
    assert r["total"] >= 30


def test_busca_sem_argumentos_e_invalida(ferr):
    r = ferr.executar("buscar_produtos", {})
    assert r["ok"] is False and r["erro"]["codigo"] == "ARGUMENTO_INVALIDO"


# --- preços, promoções e PIX (I4, DD2) -------------------------------------------------


def test_preco_promocional_formatado(ferr):
    p = ferr.executar("detalhar_produto", {"product_id": 90})["produto"]
    assert p["preco_tabela"] == "R$ 2.399,00"
    assert p["promocao"] == {"desconto_percent": 18, "descricao": "Desconto Exclusivo"}
    assert p["preco_promocional"] == "R$ 1.967,18"
    p = ferr.executar("detalhar_produto", {"product_id": 127})["produto"]
    assert p["preco_promocional"] == "R$ 323,10"


def test_pix_nao_soma_com_promocao(ferr):
    com_promo = ferr.executar("detalhar_produto", {"product_id": 90})["produto"]
    assert "preco_pix" not in com_promo
    assert "PIX" in com_promo["observacao_pix"]
    sem_promo = ferr.executar("detalhar_produto", {"product_id": 95})["produto"]
    assert sem_promo["preco_pix"] == "R$ 2.089,05"
    assert "preco_promocional" not in sem_promo


def test_promocao_inativa_e_ignorada(ferr):
    p = ferr.executar("detalhar_produto", {"product_id": 93})["produto"]  # promos 6 e 23, inativas
    assert "promocao" not in p and "preco_promocional" not in p


def test_maior_desconto_entre_ativas(tmp_path):
    destino = tmp_path / "data"
    shutil.copytree(DADOS_DIR_PADRAO, destino)
    arq = destino / "desafio_tecnico_ai_eng - promotions.csv"
    texto = arq.read_text(encoding="utf-8").rstrip() + "\n26,90,25,Outra,1\n27,90,5,Menor,1\n"
    arq.write_text(texto, encoding="utf-8")
    f = Ferramentas(carregar_dados(destino))
    p = f.executar("detalhar_produto", {"product_id": 90})["produto"]
    assert p["promocao"]["desconto_percent"] == 25
    assert p["preco_promocional"] == "R$ 1.799,25"


def test_listar_promocoes_ativas(ferr):
    r = ferr.executar("listar_promocoes_ativas", {})
    assert r["ok"] is True
    assert sorted(i["product_id"] for i in r["promocoes"]) == [90, 94, 121, 127]
    por_id = {i["product_id"]: i for i in r["promocoes"]}
    assert por_id[90]["preco_promocional"] == "R$ 1.967,18"
    assert por_id[94]["preco_promocional"] == "R$ 5.519,08"
    assert por_id[127]["desconto_percent"] == 10


# --- disponibilidade (DD9) -------------------------------------------------------------


@pytest.mark.parametrize(
    "product_id,codigo",
    [(95, "disponivel"), (96, "esgotado"), (130, "em_breve"), (136, "descontinuado"), (113, "descontinuado")],
)
def test_disponibilidade(ferr, product_id, codigo):
    p = ferr.executar("detalhar_produto", {"product_id": product_id})["produto"]
    assert p["disponibilidade"]["codigo"] == codigo
    assert p["disponibilidade"]["rotulo"]


# --- detalhar_produto ------------------------------------------------------------------


def test_detalhar_por_nome(ferr):
    r = ferr.executar("detalhar_produto", {"nome": "takamine gd 20"})
    assert r["ok"] and r["produto"]["product_id"] == 95
    assert r["produto"]["especificacoes"]["top"]
    assert r["produto"]["descricao"]


def test_detalhar_por_nome_ambiguo(ferr):
    r = ferr.executar("detalhar_produto", {"nome": "bass"})
    assert r["ok"] and r["ambiguo"] is True and len(r["candidatos"]) >= 3


def test_detalhar_inexistente(ferr):
    r = ferr.executar("detalhar_produto", {"product_id": 9999})
    assert r["ok"] is False and r["erro"]["codigo"] == "PRODUTO_NAO_ENCONTRADO"
    r = ferr.executar("detalhar_produto", {"nome": "zzzzqqq"})
    assert r["erro"]["codigo"] == "PRODUTO_NAO_ENCONTRADO"


def test_detalhar_sem_argumentos(ferr):
    r = ferr.executar("detalhar_produto", {})
    assert r["erro"]["codigo"] == "ARGUMENTO_INVALIDO"


# --- despachante (I5) ------------------------------------------------------------------


def test_ferramenta_desconhecida(ferr):
    r = ferr.executar("apagar_tudo", {})
    assert r["ok"] is False and r["erro"]["codigo"] == "FERRAMENTA_DESCONHECIDA"


@pytest.mark.parametrize(
    "argumentos",
    [
        {"foo": 1},
        {"texto": 123},
        {"texto": "a", "preco_min": "abc"},
        {"texto": "a", "so_disponiveis": "talvez"},
        "texto",
        [1],
    ],
)
def test_argumentos_invalidos_viram_erro_estruturado(ferr, argumentos):
    r = ferr.executar("buscar_produtos", argumentos)
    assert r["ok"] is False and r["erro"]["codigo"] == "ARGUMENTO_INVALIDO"
    assert set(r["erro"]) == {"codigo", "mensagem"}


def test_argumentos_none_equivale_a_vazio(ferr):
    r = ferr.executar("listar_promocoes_ativas", None)
    assert r["ok"] is True


def test_erro_interno_nao_vaza_excecao(ferr, monkeypatch):
    def quebra(self, **kw):
        raise RuntimeError("segredo interno /etc/senha")

    monkeypatch.setattr(Ferramentas, "listar_promocoes_ativas", quebra)
    r = ferr.executar("listar_promocoes_ativas", {})
    assert r["ok"] is False and r["erro"]["codigo"] == "ERRO_INTERNO"
    assert "segredo" not in str(r)


def test_schemas_neutros_de_provedor(ferr):
    nomes = {s["name"] for s in ferr.schemas}
    assert {"buscar_produtos", "detalhar_produto", "listar_promocoes_ativas"} <= nomes
    for s in ferr.schemas:
        assert set(s) == {"name", "description", "input_schema"}
        assert s["input_schema"]["type"] == "object"
        assert len(s["description"]) > 40
