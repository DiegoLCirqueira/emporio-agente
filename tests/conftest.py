import os

import pytest
from dotenv import load_dotenv

from emporio_agente.config import ENV_PADRAO

# Os e2e precisam da chave que pode estar só no .env (I2). override=False mantém o ambiente.
load_dotenv(ENV_PADRAO, override=False)


def pytest_collection_modifyitems(config, items):
    """Pula os testes e2e quando não há ANTHROPIC_API_KEY (chamam a API paga)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    skip = pytest.mark.skip(reason="ANTHROPIC_API_KEY não definida")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)
