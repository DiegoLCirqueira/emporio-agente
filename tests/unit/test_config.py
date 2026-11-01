from datetime import date
from pathlib import Path

import pytest

from emporio_agente.config import MODELO_PADRAO_POR_PROVEDOR, Config, ConfigError

CHAVES = (
    "EMPORIO_PROVEDOR",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "EMPORIO_MODELO",
    "REFERENCE_DATE",
    "HISTORICO_MAX_TURNOS",
    "SALVAR_TRANSCRIPTS",
    "EMPORIO_DADOS_DIR",
)


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    for chave in CHAVES:
        monkeypatch.delenv(chave, raising=False)


def escrever_env(tmp_path, conteudo):
    arquivo = tmp_path / ".env"
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


def test_padroes_sem_env(tmp_path):
    cfg = Config.from_env(env_file=tmp_path / "nao_existe.env")
    assert cfg.provedor == "gemini"
    assert cfg.modelo == MODELO_PADRAO_POR_PROVEDOR["gemini"] == "gemini-3.8-flash"
    assert cfg.reference_date == date(2026, 3, 31)
    assert cfg.historico_max_turnos == 10
    assert cfg.salvar_transcripts is False
    assert cfg.anthropic_api_key is None
    assert (cfg.dados_dir / "desafio_tecnico_ai_eng - products.csv").exists()


def test_le_valores_do_env(tmp_path):
    env = escrever_env(
        tmp_path,
        "ANTHROPIC_API_KEY=sk-teste\nEMPORIO_MODELO=outro-modelo\n"
        "REFERENCE_DATE=2026-04-15\nHISTORICO_MAX_TURNOS=4\nSALVAR_TRANSCRIPTS=true\n",
    )
    cfg = Config.from_env(env_file=env)
    assert cfg.anthropic_api_key == "sk-teste"
    assert cfg.modelo == "outro-modelo"
    assert cfg.reference_date == date(2026, 4, 15)
    assert cfg.historico_max_turnos == 4
    assert cfg.salvar_transcripts is True


def test_variavel_de_ambiente_tem_prioridade_sobre_env(tmp_path, monkeypatch):
    env = escrever_env(tmp_path, "EMPORIO_MODELO=do-arquivo\n")
    monkeypatch.setenv("EMPORIO_MODELO", "do-ambiente")
    assert Config.from_env(env_file=env).modelo == "do-ambiente"


def test_from_env_nao_altera_os__environ(tmp_path):
    import os

    env = escrever_env(tmp_path, "EMPORIO_MODELO=do-arquivo\n")
    Config.from_env(env_file=env)
    assert "EMPORIO_MODELO" not in os.environ


def test_chave_vazia_vira_none(tmp_path):
    env = escrever_env(tmp_path, "ANTHROPIC_API_KEY=\n")
    assert Config.from_env(env_file=env).anthropic_api_key is None


def test_data_invalida_gera_erro_claro(tmp_path):
    env = escrever_env(tmp_path, "REFERENCE_DATE=31/03/2026\n")
    with pytest.raises(ConfigError, match="REFERENCE_DATE"):
        Config.from_env(env_file=env)


@pytest.mark.parametrize("valor", ["abc", "0", "-3", "2.5"])
def test_historico_invalido(tmp_path, valor):
    env = escrever_env(tmp_path, f"HISTORICO_MAX_TURNOS={valor}\n")
    with pytest.raises(ConfigError, match="HISTORICO_MAX_TURNOS"):
        Config.from_env(env_file=env)


@pytest.mark.parametrize("valor,esperado", [("TRUE", True), ("1", True), ("false", False), ("0", False)])
def test_booleano(tmp_path, valor, esperado):
    env = escrever_env(tmp_path, f"SALVAR_TRANSCRIPTS={valor}\n")
    assert Config.from_env(env_file=env).salvar_transcripts is esperado


def test_booleano_invalido(tmp_path):
    env = escrever_env(tmp_path, "SALVAR_TRANSCRIPTS=talvez\n")
    with pytest.raises(ConfigError, match="SALVAR_TRANSCRIPTS"):
        Config.from_env(env_file=env)


def test_dados_dir_configuravel(tmp_path):
    env = escrever_env(tmp_path, f"EMPORIO_DADOS_DIR={tmp_path}\n")
    assert Config.from_env(env_file=env).dados_dir == Path(tmp_path)


def test_config_e_imutavel(tmp_path):
    cfg = Config.from_env(env_file=tmp_path / "x.env")
    with pytest.raises(Exception):
        cfg.modelo = "x"


# --- provedor, chaves e modelo padrão --------------------------------------------------


def test_modelo_vazio_usa_o_padrao_do_provedor(tmp_path):
    env = escrever_env(tmp_path, "EMPORIO_PROVEDOR=anthropic\nEMPORIO_MODELO=\n")
    cfg = Config.from_env(env_file=env)
    assert cfg.provedor == "anthropic" and cfg.modelo == "claude-haiku-5-5"
    assert Config.from_env(env_file=escrever_env(tmp_path, "EMPORIO_MODELO=\n")).modelo == "gemini-3.8-flash"


def test_modelo_explicito_do_provedor_e_respeitado(tmp_path):
    env = escrever_env(tmp_path, "EMPORIO_MODELO=gemini-3.8-flash-lite\n")
    assert Config.from_env(env_file=env).modelo == "gemini-3.8-flash-lite"


@pytest.mark.parametrize("provedor", ["Gemini", " ANTHROPIC "])
def test_provedor_normalizado(tmp_path, provedor):
    env = escrever_env(tmp_path, f"EMPORIO_PROVEDOR={provedor}\n")
    assert Config.from_env(env_file=env).provedor == provedor.strip().lower()


def test_provedor_invalido(tmp_path):
    env = escrever_env(tmp_path, "EMPORIO_PROVEDOR=openai\n")
    with pytest.raises(ConfigError, match="EMPORIO_PROVEDOR"):
        Config.from_env(env_file=env)


def test_modelo_claude_com_provedor_gemini_e_erro_claro(tmp_path):
    # é exatamente o .env atual do Diego: EMPORIO_MODELO=claude-haiku-5-5 sem EMPORIO_PROVEDOR
    env = escrever_env(tmp_path, "EMPORIO_MODELO=claude-haiku-5-5\n")
    with pytest.raises(ConfigError) as info:
        Config.from_env(env_file=env)
    msg = str(info.value)
    assert "EMPORIO_MODELO" in msg and "gemini" in msg and "vazio" in msg


def test_modelo_gemini_com_provedor_anthropic_e_erro_claro(tmp_path):
    env = escrever_env(tmp_path, "EMPORIO_PROVEDOR=anthropic\nEMPORIO_MODELO=gemini-3.8-flash\n")
    with pytest.raises(ConfigError, match="EMPORIO_MODELO"):
        Config.from_env(env_file=env)


def test_chave_exigida_e_a_do_provedor_escolhido(tmp_path):
    env = escrever_env(tmp_path, "GEMINI_API_KEY=chave-gemini\nANTHROPIC_API_KEY=chave-claude\n")
    cfg = Config.from_env(env_file=env)
    assert cfg.variavel_chave == "GEMINI_API_KEY" and cfg.chave_api == "chave-gemini"
    env = escrever_env(tmp_path, "EMPORIO_PROVEDOR=anthropic\nANTHROPIC_API_KEY=chave-claude\n")
    cfg = Config.from_env(env_file=env)
    assert cfg.variavel_chave == "ANTHROPIC_API_KEY" and cfg.chave_api == "chave-claude"


def test_chave_do_outro_provedor_nao_conta(tmp_path):
    cfg = Config.from_env(env_file=escrever_env(tmp_path, "ANTHROPIC_API_KEY=chave-claude\n"))
    assert cfg.chave_api is None


def test_repr_nao_expoe_chaves(tmp_path):
    env = escrever_env(tmp_path, "GEMINI_API_KEY=segredo-gemini\nANTHROPIC_API_KEY=segredo-claude\n")
    texto = repr(Config.from_env(env_file=env))
    assert "segredo-gemini" not in texto and "segredo-claude" not in texto
