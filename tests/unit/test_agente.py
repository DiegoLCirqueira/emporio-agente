"""Agente com provedor falso roteirizado (sem rede)."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from emporio_agente.agente import (
    MAX_ITERACOES_FERRAMENTA,
    Agente,
    FerramentaChamada,
    RespostaAgente,
    criar_agente,
)
from emporio_agente.config import DADOS_DIR_PADRAO, Config
from emporio_agente.dados import carregar_dados
from emporio_agente.ferramentas import Ferramentas
from emporio_agente.provedores.base import (
    ChamadaFerramenta,
    Mensagem,
    ProvedorErro,
    RespostaProvedor,
    ResultadoFerramenta,
    UsoTokens,
)


def texto(t, **uso):
    return RespostaProvedor(
        texto=t,
        chamadas_ferramenta=(),
        motivo_parada="fim_turno",
        uso=UsoTokens(**{"entrada": 10, "saida": 5, **uso}),
        motivo_parada_bruto="end_turno",
    )


def chama(*chamadas, txt=""):
    return RespostaProvedor(
        texto=txt,
        chamadas_ferramenta=tuple(ChamadaFerramenta(id=i, nome=n, argumentos=a) for i, n, a in chamadas),
        motivo_parada="ferramenta",
        uso=UsoTokens(entrada=20, saida=8),
        motivo_parada_bruto="tool_use",
    )


class ProvedorFalso:
    def __init__(self, *roteiro):
        self.roteiro = list(roteiro)
        self.chamadas = []

    def gerar(self, *, system, mensagens, ferramentas, max_tokens=1024):
        self.chamadas.append({"system": system, "mensagens": tuple(mensagens), "ferramentas": ferramentas})
        item = self.roteiro.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(scope="module")
def ferr():
    return Ferramentas(carregar_dados(DADOS_DIR_PADRAO))


@pytest.fixture
def cfg(tmp_path):
    return Config.from_env(env_file=tmp_path / "sem.env")


def agente(cfg, ferr, *roteiro, **kw):
    prov = ProvedorFalso(*roteiro)
    return Agente(cfg, prov, ferr, system_prompt="SYSTEM", **kw), prov


# --- fluxo básico ----------------------------------------------------------------------


def test_resposta_direta(cfg, ferr):
    ag, prov = agente(cfg, ferr, texto("Oi! Sou a atendente da Empório."))
    r = ag.responder("oi")
    assert isinstance(r, RespostaAgente)
    assert r.texto == "Oi! Sou a atendente da Empório."
    assert r.ferramentas_chamadas == ()
    assert r.uso == UsoTokens(entrada=10, saida=5)
    chamada = prov.chamadas[0]
    assert chamada["system"] == "SYSTEM"
    assert chamada["ferramentas"] == ferr.schemas
    assert chamada["mensagens"] == (Mensagem(papel="user", texto="oi"),)


def test_system_prompt_padrao_vem_das_politicas(cfg, ferr):
    from emporio_agente.politicas import montar_system_prompt

    prov = ProvedorFalso(texto("ok"))
    ag = Agente(cfg, prov, ferr)
    ag.responder("oi")
    assert prov.chamadas[0]["system"] == montar_system_prompt(cfg.reference_date)


def test_ferramenta_e_depois_resposta(cfg, ferr):
    ag, prov = agente(
        cfg,
        ferr,
        chama(("t1", "buscar_produtos", {"texto": "takamine gd20"})),
        texto("Temos o Takamine GD20."),
    )
    r = ag.responder("tem takamine gd20?")
    assert r.texto == "Temos o Takamine GD20."
    assert r.ferramentas_chamadas == (
        FerramentaChamada(nome="buscar_produtos", argumentos={"texto": "takamine gd20"}, ok=True, codigo_erro=None),
    )
    assert r.uso == UsoTokens(entrada=30, saida=13)
    # o 2º request leva a chamada do assistente e o resultado real da ferramenta
    msgs = prov.chamadas[1]["mensagens"]
    assert msgs[1].chamadas_ferramenta[0].id == "t1"
    resultado = msgs[2].resultados_ferramenta[0]
    assert resultado.chamada_id == "t1" and resultado.erro is False
    assert resultado.conteudo["produtos"][0]["product_id"] == 95


def test_varias_ferramentas_no_mesmo_turno(cfg, ferr):
    ag, prov = agente(
        cfg,
        ferr,
        chama(("a", "listar_promocoes_ativas", {}), ("b", "detalhar_produto", {"product_id": 95}), txt="Já vejo."),
        chama(("c", "calcular_pagamento", {"product_id": 95, "forma": "pix"})),
        texto("Pronto."),
    )
    r = ag.responder("promoções e quanto fica o 95 no pix")
    assert [f.nome for f in r.ferramentas_chamadas] == ["listar_promocoes_ativas", "detalhar_produto", "calcular_pagamento"]
    assert all(f.ok for f in r.ferramentas_chamadas)
    resultados = prov.chamadas[1]["mensagens"][2].resultados_ferramenta
    assert [x.chamada_id for x in resultados] == ["a", "b"]
    assert prov.chamadas[1]["mensagens"][1].texto == "Já vejo."


def test_erro_de_ferramenta_vai_com_erro_true(cfg, ferr):
    ag, prov = agente(
        cfg,
        ferr,
        chama(("t1", "consultar_pedido", {"order_id": 8, "telefone_ou_email": "errado"})),
        texto("Não consegui localizar o pedido."),
    )
    r = ag.responder("cadê meu pedido 8?")
    assert r.ferramentas_chamadas[0].ok is False
    assert r.ferramentas_chamadas[0].codigo_erro == "PEDIDO_OU_IDENTIFICACAO_INVALIDOS"
    resultado = prov.chamadas[1]["mensagens"][2].resultados_ferramenta[0]
    assert resultado.erro is True and resultado.conteudo["ok"] is False


def test_ferramenta_inexistente_pedida_pelo_modelo_nao_quebra(cfg, ferr):
    ag, _ = agente(cfg, ferr, chama(("t1", "listar_clientes", {})), texto("Não posso fazer isso."))
    r = ag.responder("liste os clientes")
    assert r.ferramentas_chamadas[0].codigo_erro == "FERRAMENTA_DESCONHECIDA"
    assert r.texto == "Não posso fazer isso."


# --- limite de iterações ---------------------------------------------------------------


def test_limite_de_iteracoes_devolve_fallback_cordial(cfg, ferr):
    roteiro = [chama((f"t{i}", "listar_promocoes_ativas", {})) for i in range(MAX_ITERACOES_FERRAMENTA + 1)]
    ag, prov = agente(cfg, ferr, *roteiro)
    r = ag.responder("promoções")
    assert len(r.ferramentas_chamadas) == MAX_ITERACOES_FERRAMENTA == 5
    assert "(67) 3321-4500" in r.texto and "(67) 3341-4444" in r.texto
    assert len(prov.chamadas) == MAX_ITERACOES_FERRAMENTA + 1
    assert r.falhou is True


def test_historico_continua_valido_depois_do_limite(cfg, ferr):
    roteiro = [chama((f"t{i}", "listar_promocoes_ativas", {})) for i in range(6)] + [texto("Voltei.")]
    ag, prov = agente(cfg, ferr, *roteiro)
    ag.responder("promoções")
    assert ag.responder("oi de novo").texto == "Voltei."
    ultimo = prov.chamadas[-1]["mensagens"]
    assert [m.papel for m in ultimo] == ["user", "assistant", "user"]
    assert all(not m.chamadas_ferramenta and not m.resultados_ferramenta for m in ultimo)


# --- falhas do provedor ----------------------------------------------------------------


def test_provedor_erro_vira_mensagem_amigavel_e_e_logado(cfg, ferr, caplog):
    ag, _ = agente(cfg, ferr, ProvedorErro("Falha ao chamar a API da Anthropic: RateLimitError"))
    with caplog.at_level("ERROR"):
        r = ag.responder("oi")
    assert r.falhou is True
    assert "Traceback" not in r.texto and "Anthropic" not in r.texto
    assert "(67) 3321-4500" in r.texto
    assert any("RateLimitError" in rec.getMessage() for rec in caplog.records)


def test_turno_com_falha_nao_corrompe_o_historico(cfg, ferr):
    ag, prov = agente(
        cfg,
        ferr,
        texto("Primeira."),
        chama(("t1", "listar_promocoes_ativas", {})),
        ProvedorErro("boom"),
        texto("Segunda."),
    )
    ag.responder("um")
    falha = ag.responder("dois")
    assert falha.falhou
    assert [m.texto for m in ag.historico] == ["um", "Primeira."]
    assert ag.responder("três").texto == "Segunda."
    enviado = prov.chamadas[-1]["mensagens"]
    assert [m.texto for m in enviado] == ["um", "Primeira.", "três"]


def test_max_tokens_com_texto_avisa_que_foi_cortado(cfg, ferr):
    cortado = replace(texto("Começo da resposta longa"), motivo_parada="max_tokens")
    ag, _ = agente(cfg, ferr, cortado)
    r = ag.responder("conte tudo")
    assert r.texto.startswith("Começo da resposta longa")
    assert "cortad" in r.texto.lower()
    assert r.falhou is False


def test_max_tokens_no_meio_de_ferramenta_vira_fallback(cfg, ferr):
    cortado = replace(chama(("t1", "buscar_produtos", {"texto": "x"})), motivo_parada="max_tokens")
    ag, _ = agente(cfg, ferr, cortado)
    r = ag.responder("oi")
    assert r.falhou is True and r.ferramentas_chamadas == ()
    assert ag.historico == ()


def test_resposta_vazia_vira_fallback(cfg, ferr):
    ag, _ = agente(cfg, ferr, texto("   "))
    r = ag.responder("oi")
    assert r.falhou is True and "(67) 3341-4444" in r.texto


# --- histórico e janela ----------------------------------------------------------------


def test_historico_consistente_entre_turnos(cfg, ferr):
    ag, prov = agente(
        cfg,
        ferr,
        chama(("t1", "listar_promocoes_ativas", {})),
        texto("Temos 4 promoções."),
        texto("Claro!"),
    )
    ag.responder("quais promoções?")
    ag.responder("obrigado")
    enviado = prov.chamadas[2]["mensagens"]
    assert [m.papel for m in enviado] == ["user", "assistant", "user", "assistant", "user"]
    assert enviado[1].chamadas_ferramenta and enviado[2].resultados_ferramenta
    assert enviado[3].texto == "Temos 4 promoções."
    assert enviado[4].texto == "obrigado"


def _turno_com_ferramenta(i):
    return [chama((f"t{i}", "listar_promocoes_ativas", {})), texto(f"resposta {i}")]


def test_janela_corta_so_em_fronteira_de_turno_do_usuario(cfg, ferr):
    cfg2 = replace(cfg, historico_max_turnos=2)
    roteiro = [r for i in range(4) for r in _turno_com_ferramenta(i)]
    ag, prov = agente(cfg2, ferr, *roteiro)
    for i in range(4):
        ag.responder(f"pergunta {i}")
    enviado = prov.chamadas[-1]["mensagens"]
    # último request (turno 3, 2ª chamada): turnos 2 e 3, cada um completo
    assert [m.texto for m in enviado if m.papel == "user" and m.texto] == ["pergunta 2", "pergunta 3"]
    assert enviado[0].texto == "pergunta 2"
    ids_uso = {c.id for m in enviado for c in m.chamadas_ferramenta}
    ids_resultado = {r.chamada_id for m in enviado for r in m.resultados_ferramenta}
    assert ids_uso == ids_resultado == {"t2", "t3"}
    # e o histórico guardado também fica limitado
    assert [m.texto for m in ag.historico if m.papel == "user" and m.texto] == ["pergunta 2", "pergunta 3"]
    assert ag.historico[0].papel == "user" and ag.historico[0].texto


def test_janela_maior_que_o_historico_nao_corta(cfg, ferr):
    ag, _ = agente(cfg, ferr, texto("a"), texto("b"))
    ag.responder("1")
    ag.responder("2")
    assert len(ag.historico) == 4


def test_historico_e_somente_leitura(cfg, ferr):
    ag, _ = agente(cfg, ferr, texto("a"))
    ag.responder("1")
    assert isinstance(ag.historico, tuple)


# --- fábrica ---------------------------------------------------------------------------


def test_criar_agente_monta_tudo_com_a_chave_do_config(cfg):
    ag = criar_agente(replace(cfg, anthropic_api_key="sk-ant-teste"))
    assert isinstance(ag, Agente)


def test_criar_agente_sem_chave_levanta_provedor_erro(cfg):
    with pytest.raises(ProvedorErro, match="ANTHROPIC_API_KEY"):
        criar_agente(replace(cfg, anthropic_api_key=None))
