"""CLI com agente falso (sem rede e sem .env real)."""

import re
import subprocess
import sys
from dataclasses import replace

import pytest

from emporio_agente.agente import FerramentaChamada, RespostaAgente
from emporio_agente.cli import main
from emporio_agente.config import Config
from emporio_agente.provedores.base import ProvedorErro, UsoTokens


class AgenteFalso:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.recebidas = []

    def responder(self, mensagem):
        self.recebidas.append(mensagem)
        return self.respostas.pop(0) if self.respostas else resposta("ok")


def resposta(texto, ferramentas=(), falhou=False):
    return RespostaAgente(texto, tuple(ferramentas), UsoTokens(), falhou=falhou)


@pytest.fixture
def cfg(tmp_path):
    return replace(Config.from_env(env_file=tmp_path / "sem.env"), anthropic_api_key="sk-teste")


def rodar(argv, cfg, agente=None, **kw):
    fabrica = (lambda c: agente) if agente is not None else kw.pop("fabrica", None)
    return main(argv, config=cfg, fabrica=fabrica, **kw)


# --- --mensagem ------------------------------------------------------------------------


def test_mensagem_unica(cfg, capsys):
    ag = AgenteFalso(resposta("Olá! Como posso ajudar?"))
    codigo = rodar(["--mensagem", "oi"], cfg, ag)
    assert codigo == 0
    assert ag.recebidas == ["oi"]
    assert capsys.readouterr().out.strip() == "Olá! Como posso ajudar?"


def test_mensagem_unica_com_falha_sai_com_codigo_1(cfg, capsys):
    ag = AgenteFalso(resposta("Desculpe, problema técnico.", falhou=True))
    assert rodar(["-m", "oi"], cfg, ag) == 1
    assert "Desculpe" in capsys.readouterr().out


# --- --mostrar-ferramentas -------------------------------------------------------------


def test_mostrar_ferramentas(cfg, capsys):
    ferramentas = [
        FerramentaChamada("buscar_produtos", {"texto": "violão"}, True),
        FerramentaChamada("consultar_pedido", {"order_id": 8, "telefone_ou_email": "x"}, False, "PEDIDO_OU_IDENTIFICACAO_INVALIDOS"),
    ]
    ag = AgenteFalso(resposta("Resposta.", ferramentas))
    rodar(["--mensagem", "oi", "--mostrar-ferramentas"], cfg, ag)
    saida = capsys.readouterr().out
    assert 'buscar_produtos {"texto": "violão"} -> ok' in saida
    assert "consultar_pedido" in saida and "-> erro PEDIDO_OU_IDENTIFICACAO_INVALIDOS" in saida
    assert saida.index("buscar_produtos") < saida.index("Resposta.")


def test_sem_a_flag_nao_mostra_ferramentas(cfg, capsys):
    ag = AgenteFalso(resposta("Resposta.", [FerramentaChamada("buscar_produtos", {}, True)]))
    rodar(["--mensagem", "oi"], cfg, ag)
    assert "buscar_produtos" not in capsys.readouterr().out


def test_mostrar_ferramentas_avisa_quando_nenhuma_foi_chamada(cfg, capsys):
    rodar(["-m", "oi", "--mostrar-ferramentas"], cfg, AgenteFalso(resposta("Oi.")))
    assert "nenhuma ferramenta" in capsys.readouterr().out.lower()


# --- REPL ------------------------------------------------------------------------------


def entradas(monkeypatch, *linhas):
    fila = list(linhas)

    def fake_input(prompt=""):
        item = fila.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr("builtins.input", fake_input)


def test_repl_conversa_e_sai_com_sair(cfg, capsys, monkeypatch):
    ag = AgenteFalso(resposta("Resposta 1"), resposta("Resposta 2"))
    entradas(monkeypatch, "primeira", "", "segunda", "SAIR")
    assert rodar([], cfg, ag) == 0
    saida = capsys.readouterr().out
    assert ag.recebidas == ["primeira", "segunda"]  # linha vazia é ignorada
    assert "Resposta 1" in saida and "Resposta 2" in saida
    assert "sair" in saida.lower()  # saudação explica como encerrar


@pytest.mark.parametrize("encerramento", [EOFError(), KeyboardInterrupt()])
def test_repl_encerra_sem_traceback_em_eof_e_ctrl_c(cfg, capsys, monkeypatch, encerramento):
    entradas(monkeypatch, encerramento)
    assert rodar([], cfg, AgenteFalso()) == 0
    capturado = capsys.readouterr()
    assert "Traceback" not in capturado.out + capturado.err


def test_ctrl_c_durante_a_resposta_tambem_encerra(cfg, capsys, monkeypatch):
    class Interrompido(AgenteFalso):
        def responder(self, mensagem):
            raise KeyboardInterrupt

    entradas(monkeypatch, "oi")
    assert rodar([], cfg, Interrompido()) == 0
    assert "Traceback" not in capsys.readouterr().err


def test_repl_mostra_ferramentas_a_cada_turno(cfg, capsys, monkeypatch):
    ag = AgenteFalso(resposta("A", [FerramentaChamada("listar_promocoes_ativas", {}, True)]))
    entradas(monkeypatch, "promoções", "sair")
    rodar(["--mostrar-ferramentas"], cfg, ag)
    assert "listar_promocoes_ativas {} -> ok" in capsys.readouterr().out


# --- sem chave / configuração ----------------------------------------------------------


def test_sem_chave_explica_o_env_e_sai_com_2(cfg, capsys):
    sem_chave = replace(cfg, anthropic_api_key=None)
    codigo = main(["--mensagem", "oi"], config=sem_chave)  # fábrica real: levanta ProvedorErro
    capturado = capsys.readouterr()
    assert codigo == 2
    assert ".env" in capturado.err and "ANTHROPIC_API_KEY" in capturado.err
    assert ".env.example" in capturado.err
    assert "Traceback" not in capturado.err + capturado.out


def test_erro_de_configuracao_sai_com_2(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("REFERENCE_DATE", "31/03/2026")
    codigo = main(["--mensagem", "oi"])
    capturado = capsys.readouterr()
    assert codigo == 2 and "REFERENCE_DATE" in capturado.err
    assert "Traceback" not in capturado.err


def test_provedor_erro_na_criacao_nao_vira_traceback(cfg, capsys):
    def fabrica(_):
        raise ProvedorErro("qualquer coisa")

    assert main(["-m", "oi"], config=cfg, fabrica=fabrica) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_pasta_de_dados_inexistente_sai_com_2_sem_traceback(cfg, tmp_path, capsys):
    ruim = replace(cfg, dados_dir=tmp_path / "nao_existe")
    assert main(["-m", "oi"], config=ruim) == 2
    err = capsys.readouterr().err
    assert "nao_existe" in err and "Traceback" not in err


# --- transcripts -----------------------------------------------------------------------


def test_transcript_gravado_quando_habilitado(cfg, tmp_path, monkeypatch, capsys):
    cfg2 = replace(cfg, salvar_transcripts=True)
    pasta = tmp_path / "transcripts"
    ag = AgenteFalso(resposta("Temos sim.", [FerramentaChamada("buscar_produtos", {"texto": "gd20"}, True)]), resposta("De nada!"))
    entradas(monkeypatch, "tem gd20?", "obrigado", "sair")
    rodar([], cfg2, ag, transcripts_dir=pasta)
    arquivos = list(pasta.glob("*.md"))
    assert len(arquivos) == 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{6}\.md", arquivos[0].name)
    conteudo = arquivos[0].read_text(encoding="utf-8")
    assert "tem gd20?" in conteudo and "Temos sim." in conteudo
    assert 'buscar_produtos {"texto": "gd20"} -> ok' in conteudo
    assert "obrigado" in conteudo and "De nada!" in conteudo


def test_transcript_em_mensagem_unica(cfg, tmp_path):
    cfg2 = replace(cfg, salvar_transcripts=True)
    pasta = tmp_path / "t"
    rodar(["-m", "oi"], cfg2, AgenteFalso(resposta("Olá!")), transcripts_dir=pasta)
    assert len(list(pasta.glob("*.md"))) == 1


def test_sem_transcript_por_padrao(cfg, tmp_path):
    pasta = tmp_path / "t"
    rodar(["-m", "oi"], cfg, AgenteFalso(resposta("Olá!")), transcripts_dir=pasta)
    assert not pasta.exists()


def test_transcript_so_e_criado_quando_ha_conversa(cfg, tmp_path, monkeypatch):
    cfg2 = replace(cfg, salvar_transcripts=True)
    pasta = tmp_path / "t"
    entradas(monkeypatch, "sair")
    rodar([], cfg2, AgenteFalso(), transcripts_dir=pasta)
    assert not pasta.exists() or not list(pasta.glob("*.md"))


# --- execução como módulo --------------------------------------------------------------


def test_python_dash_m_sem_chave_sai_com_2(tmp_path):
    ambiente = {"PATH": "", "SYSTEMROOT": "C:\\Windows"}
    proc = subprocess.run(
        [sys.executable, "-m", "emporio_agente", "--mensagem", "oi"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**ambiente, "ANTHROPIC_API_KEY": ""},
        cwd=tmp_path,
    )
    assert proc.returncode == 2  # ANTHROPIC_API_KEY vazia no ambiente vence o .env
    assert "Traceback" not in proc.stderr
