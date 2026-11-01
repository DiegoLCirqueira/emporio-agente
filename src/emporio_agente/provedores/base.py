"""Contrato neutro de provedor de LLM e tipos normalizados de mensagem e resposta."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

MotivoParada = Literal["fim_turno", "ferramenta", "max_tokens", "outro"]


class ProvedorErro(Exception):
    """Falha ao falar com o provedor (rede, autenticação, limite, resposta inválida)."""


@dataclass(frozen=True)
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos: dict[str, Any]


@dataclass(frozen=True)
class ResultadoFerramenta:
    chamada_id: str
    conteudo: dict[str, Any]
    erro: bool = False


@dataclass(frozen=True)
class Mensagem:
    """Mensagem neutra do histórico.

    - user: `texto` (fala do cliente) ou `resultados_ferramenta` (respostas às chamadas).
    - assistant: `texto` e/ou `chamadas_ferramenta`.
    """

    papel: Literal["user", "assistant"]
    texto: str = ""
    chamadas_ferramenta: tuple[ChamadaFerramenta, ...] = ()
    resultados_ferramenta: tuple[ResultadoFerramenta, ...] = ()


@dataclass(frozen=True)
class UsoTokens:
    entrada: int = 0
    saida: int = 0
    cache_criacao: int = 0
    cache_leitura: int = 0


@dataclass(frozen=True)
class RespostaProvedor:
    texto: str
    chamadas_ferramenta: tuple[ChamadaFerramenta, ...]
    motivo_parada: MotivoParada
    uso: UsoTokens
    motivo_parada_bruto: str | None = None

    def como_mensagem(self) -> Mensagem:
        """Mensagem do assistente para anexar ao histórico (inclui as chamadas de ferramenta)."""
        return Mensagem(papel="assistant", texto=self.texto, chamadas_ferramenta=self.chamadas_ferramenta)


@runtime_checkable
class Provedor(Protocol):
    def gerar(
        self,
        *,
        system: str,
        mensagens: Sequence[Mensagem],
        ferramentas: Sequence[dict],
        max_tokens: int = 1024,
    ) -> RespostaProvedor:
        """Uma chamada ao modelo. `ferramentas` são os schemas neutros (name, description,
        input_schema). Levanta ProvedorErro em qualquer falha do provedor."""
        ...
