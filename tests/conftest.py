import pytest

from emporio_agente.config import Config, ConfigError

VARIAVEIS = (
    "EMPORIO_PROVEDOR",
    "EMPORIO_MODELO",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "REFERENCE_DATE",
    "HISTORICO_MAX_TURNOS",
    "SALVAR_TRANSCRIPTS",
    "EMPORIO_DADOS_DIR",
)


def _motivo_para_pular_e2e() -> str | None:
    """None se o e2e pode rodar; senão, o motivo (nunca o valor de uma chave)."""
    try:
        config = Config.from_env()  # ambiente + .env da raiz, sem alterar os.environ
    except ConfigError as e:
        return f"configuração inválida: {e}"
    if not config.chave_api:
        return f"{config.variavel_chave} não definida (provedor {config.provedor})"
    return None


@pytest.fixture(autouse=True)
def ambiente_hermetico(request, monkeypatch):
    """Testes unitários não dependem de variáveis do shell nem do .env real."""
    if "e2e" not in request.keywords:
        for nome in VARIAVEIS:
            monkeypatch.delenv(nome, raising=False)


def pytest_collection_modifyitems(config, items):
    """Pula os testes e2e quando falta a chave do provedor configurado (gastam cota da API)."""
    e2e = [item for item in items if "e2e" in item.keywords]
    if not e2e:
        return
    motivo = _motivo_para_pular_e2e()
    if motivo is None:
        return
    skip = pytest.mark.skip(reason=motivo)
    for item in e2e:
        item.add_marker(skip)
