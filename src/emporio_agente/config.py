"""Configuração do agente, lida do ambiente e do arquivo .env."""

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from dotenv import dotenv_values

RAIZ_REPO = Path(__file__).resolve().parents[2]
ENV_PADRAO = RAIZ_REPO / ".env"
DADOS_DIR_PADRAO = RAIZ_REPO / "data"

PROVEDORES = ("gemini", "anthropic")
PROVEDOR_PADRAO = "gemini"
# Modelo usado quando EMPORIO_MODELO está vazio. Fácil de trocar aqui.
MODELO_PADRAO_POR_PROVEDOR = {"gemini": "gemini-3.8-flash", "anthropic": "claude-haiku-5-5"}
VARIAVEL_CHAVE_POR_PROVEDOR = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
PREFIXO_MODELO_POR_PROVEDOR = {"gemini": "gemini", "anthropic": "claude"}
REFERENCE_DATE_PADRAO = "2026-03-31"
HISTORICO_MAX_TURNOS_PADRAO = "10"

_VERDADEIROS = {"true", "1", "sim", "yes"}
_FALSOS = {"false", "0", "nao", "não", "no"}


class ConfigError(ValueError):
    """Valor de configuração inválido."""


@dataclass(frozen=True)
class Config:
    modelo: str
    reference_date: date
    historico_max_turnos: int
    salvar_transcripts: bool
    anthropic_api_key: str | None = field(repr=False)
    dados_dir: Path
    provedor: str = PROVEDOR_PADRAO
    gemini_api_key: str | None = field(default=None, repr=False)

    @property
    def variavel_chave(self) -> str:
        """Nome da variável de ambiente com a chave do provedor escolhido."""
        return VARIAVEL_CHAVE_POR_PROVEDOR[self.provedor]

    @property
    def chave_api(self) -> str | None:
        """Chave do provedor escolhido (e só dela)."""
        return self.gemini_api_key if self.provedor == "gemini" else self.anthropic_api_key

    @classmethod
    def from_env(cls, env_file: Path | str | None = None) -> "Config":
        """Monta a configuração.

        Variáveis já definidas no ambiente têm prioridade sobre o .env. O .env é
        lido sem alterar os.environ.
        """
        arquivo = Path(env_file) if env_file is not None else ENV_PADRAO
        valores = {k: v for k, v in dotenv_values(arquivo).items() if v is not None}
        valores.update(os.environ)

        def obter(chave: str, padrao: str = "") -> str:
            return (valores.get(chave) or padrao).strip()

        provedor = obter("EMPORIO_PROVEDOR", PROVEDOR_PADRAO).lower()
        if provedor not in PROVEDORES:
            raise ConfigError(
                f"EMPORIO_PROVEDOR inválido: {provedor!r}. Use um de: {', '.join(PROVEDORES)}."
            )
        modelo = obter("EMPORIO_MODELO") or MODELO_PADRAO_POR_PROVEDOR[provedor]
        _validar_modelo(provedor, modelo)

        return cls(
            provedor=provedor,
            gemini_api_key=obter("GEMINI_API_KEY") or None,
            modelo=modelo,
            reference_date=_data("REFERENCE_DATE", obter("REFERENCE_DATE", REFERENCE_DATE_PADRAO)),
            historico_max_turnos=_inteiro_positivo(
                "HISTORICO_MAX_TURNOS", obter("HISTORICO_MAX_TURNOS", HISTORICO_MAX_TURNOS_PADRAO)
            ),
            salvar_transcripts=_booleano("SALVAR_TRANSCRIPTS", obter("SALVAR_TRANSCRIPTS", "false")),
            anthropic_api_key=obter("ANTHROPIC_API_KEY") or None,
            dados_dir=Path(obter("EMPORIO_DADOS_DIR") or DADOS_DIR_PADRAO),
        )


def _validar_modelo(provedor: str, modelo: str) -> None:
    for outro, prefixo in PREFIXO_MODELO_POR_PROVEDOR.items():
        if outro != provedor and modelo.lower().startswith(prefixo):
            raise ConfigError(
                f"EMPORIO_MODELO={modelo!r} é um modelo do provedor {outro}, mas EMPORIO_PROVEDOR={provedor}. "
                f"Deixe EMPORIO_MODELO vazio (usa {MODELO_PADRAO_POR_PROVEDOR[provedor]}) "
                f"ou defina EMPORIO_PROVEDOR={outro}."
            )


def _data(chave: str, texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ConfigError(f"{chave} inválida: {texto!r}. Use o formato AAAA-MM-DD.") from None


def _inteiro_positivo(chave: str, texto: str) -> int:
    if not texto.isdigit() or int(texto) < 1:
        raise ConfigError(f"{chave} inválido: {texto!r}. Use um inteiro maior ou igual a 1.")
    return int(texto)


def _booleano(chave: str, texto: str) -> bool:
    minusculo = texto.lower()
    if minusculo in _VERDADEIROS:
        return True
    if minusculo in _FALSOS:
        return False
    raise ConfigError(f"{chave} inválido: {texto!r}. Use true ou false.")
