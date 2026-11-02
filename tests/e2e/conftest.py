"""Fixtures dos testes e2e: modelo real, um agente novo por cenário, pausa e nova tentativa.

Os testes só rodam com a chave do provedor (tests/conftest.py pula os e2e sem ela).
Nunca imprima nem registre a chave.
"""

import time
from dataclasses import dataclass, field

import pytest

from emporio_agente.agente import MSG_COTA, MSG_ERRO_TECNICO, Agente, RespostaAgente, criar_agente
from emporio_agente.config import Config

from apoio_e2e import e_eco_do_cliente, textos_do_historico, varrer_pii

PAUSA_ENTRE_CENARIOS_S = 4
ESPERAS_RETRY_S = (10, 30, 60)  # até 3 novas tentativas, com espera crescente
PAUSA_ENTRE_TURNOS_S = 2
REFERENCE_DATE_E2E = "2026-03-31"


@pytest.fixture(autouse=True)
def ambiente_e2e(monkeypatch):
    """Data de referência fixa. EMPORIO_AGORA (data e hora) é definida só nos cenários de horário."""
    monkeypatch.setenv("REFERENCE_DATE", REFERENCE_DATE_E2E)
    monkeypatch.delenv("EMPORIO_AGORA", raising=False)


@pytest.fixture(autouse=True)
def pausa_entre_cenarios(request):
    """Respeita a cota gratuita: espera depois de cada cenário (só os marcados e2e)."""
    yield
    if request.node.get_closest_marker("e2e"):
        time.sleep(PAUSA_ENTRE_CENARIOS_S)


ECOS: list[str] = []  # ecos de telefone/e-mail digitados pelo próprio cliente (não reprovam)


def pytest_terminal_summary(terminalreporter):
    terminalreporter.section("PII: ecos do cliente (não reprovam)")
    terminalreporter.write_line(f"total de ecos: {len(ECOS)}")
    for e in ECOS:
        terminalreporter.write_line(f"  {e}")


@dataclass
class Conversa:
    """Agente novo + registro do que aconteceu. Cada `diga` já confere PII."""

    agente: Agente
    respostas: list[RespostaAgente] = field(default_factory=list)
    falas: list[str] = field(default_factory=list)

    def diga(self, mensagem: str, rastreio_permitido: tuple[str, ...] = ()) -> RespostaAgente:
        self.falas.append(mensagem)
        if self.respostas:
            time.sleep(PAUSA_ENTRE_TURNOS_S)
        resposta = self._com_retry(mensagem)
        self.respostas.append(resposta)
        self.conferir_pii(rastreio_permitido)
        return resposta

    def _com_retry(self, mensagem: str) -> RespostaAgente:
        resposta = self.agente.responder(mensagem)
        for espera in ESPERAS_RETRY_S:
            # Falha de provedor (503/504/429) descarta o turno do histórico: repetir é seguro.
            if not (resposta.falhou and resposta.texto in (MSG_ERRO_TECNICO, MSG_COTA)):
                return resposta
            time.sleep(espera)
            resposta = self.agente.responder(mensagem)
        if resposta.falhou:
            pytest.fail(
                "API indisponível ou sem cota após 3 novas tentativas "
                f"(resposta de falha do agente: {resposta.texto[:80]!r}...)"
            )
        return resposta

    @property
    def ferramentas_chamadas(self):
        return [c for r in self.respostas for c in r.ferramentas_chamadas]

    @property
    def nomes_chamados(self) -> list[str]:
        return [c.nome for c in self.ferramentas_chamadas]

    def conferir_pii(self, rastreio_permitido: tuple[str, ...] = ()) -> None:
        """Reprova se alguma resposta ou o histórico do agente vazou PII."""
        fontes = [(f"resposta {i}", r.texto) for i, r in enumerate(self.respostas)]
        fontes += textos_do_historico(self.agente.historico)
        for origem, texto in fontes:
            todos = varrer_pii(texto, rastreio_permitido)
            achados = [a for a in todos if not e_eco_do_cliente(a, self.falas)]
            ECOS.extend(f"{origem}: {a}" for a in todos if a not in achados)
            assert not achados, f"PII vazada em {origem}: {sorted(set(achados))}\n--- texto ---\n{texto}"


@pytest.fixture
def nova_conversa():
    """Fábrica de conversas com modelo real. Chame DENTRO do teste, depois de ajustar o
    ambiente (ex.: monkeypatch.setenv("EMPORIO_AGORA", ...)), pois lê o ambiente na hora."""

    def criar() -> Conversa:
        return Conversa(criar_agente(Config.from_env()))

    return criar
