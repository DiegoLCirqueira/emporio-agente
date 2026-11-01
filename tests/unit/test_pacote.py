import re

import emporio_agente


def test_versao_definida():
    assert re.fullmatch(r"\d+\.\d+\.\d+", emporio_agente.__version__)
