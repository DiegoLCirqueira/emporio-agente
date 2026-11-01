"""Agente de atendimento: loop de function calling sobre um Provedor (decisão D1)."""

import logging
from dataclasses import dataclass

from emporio_agente.config import Config
from emporio_agente.dados import carregar_dados
from emporio_agente.ferramentas import Ferramentas
from emporio_agente.politicas import montar_system_prompt
from emporio_agente.provedores.anthropic import ProvedorAnthropic
from emporio_agente.provedores.base import (
    Mensagem,
    Provedor,
    ProvedorErro,
    ResultadoFerramenta,
    UsoTokens,
)

log = logging.getLogger(__name__)

MAX_ITERACOES_FERRAMENTA = 5

CONTATOS = "WhatsApp (67) 3321-4500, telefone (67) 3341-4444 ou e-mail contato@emporiodamusica.com.br"
MSG_ERRO_TECNICO = (
    "Desculpe, tive um problema técnico e não consegui responder agora. "
    f"Pode tentar de novo em instantes? Se preferir, fale com a nossa equipe: {CONTATOS}."
)
MSG_LIMITE = (
    "Desculpe, não consegui concluir essa consulta por aqui. "
    f"Nossa equipe pode te ajudar direto: {CONTATOS}."
)
MSG_CORTADA = "\n\n(Minha resposta ficou longa e foi cortada. Se quiser, peça que eu continue ou detalhe um ponto.)"


@dataclass(frozen=True)
class FerramentaChamada:
    nome: str
    argumentos: dict
    ok: bool
    codigo_erro: str | None = None


@dataclass(frozen=True)
class RespostaAgente:
    texto: str
    ferramentas_chamadas: tuple[FerramentaChamada, ...]
    uso: UsoTokens
    falhou: bool = False


def _somar(a: UsoTokens, b: UsoTokens) -> UsoTokens:
    return UsoTokens(
        entrada=a.entrada + b.entrada,
        saida=a.saida + b.saida,
        cache_criacao=a.cache_criacao + b.cache_criacao,
        cache_leitura=a.cache_leitura + b.cache_leitura,
    )


def _inicio_de_turno(m: Mensagem) -> bool:
    """Fala do cliente (e não o tool_result, que também tem papel user)."""
    return m.papel == "user" and bool(m.texto) and not m.resultados_ferramenta


class Agente:
    def __init__(
        self,
        config: Config,
        provedor: Provedor,
        ferramentas: Ferramentas,
        system_prompt: str | None = None,
    ):
        self._config = config
        self._provedor = provedor
        self._ferramentas = ferramentas
        self._system = system_prompt if system_prompt is not None else montar_system_prompt(config.reference_date)
        self._historico: list[Mensagem] = []

    @property
    def historico(self) -> tuple[Mensagem, ...]:
        return tuple(self._historico)

    def _janela(self, mensagens: list[Mensagem]) -> list[Mensagem]:
        """Mantém só os últimos N turnos do cliente, cortando sempre numa fala do cliente,
        nunca entre um tool_use e o seu tool_result."""
        inicios = [i for i, m in enumerate(mensagens) if _inicio_de_turno(m)]
        n = self._config.historico_max_turnos
        return mensagens if len(inicios) <= n else mensagens[inicios[-n] :]

    def responder(self, mensagem: str) -> RespostaAgente:
        base = self._janela([*self._historico, Mensagem(papel="user", texto=mensagem)])
        novas: list[Mensagem] = []
        chamadas: list[FerramentaChamada] = []
        uso = UsoTokens()
        rodadas = 0
        while True:
            try:
                r = self._provedor.gerar(
                    system=self._system,
                    mensagens=[*base, *novas],
                    ferramentas=self._ferramentas.schemas,
                )
            except ProvedorErro as e:
                log.exception("Falha do provedor, turno descartado: %s", e)
                return RespostaAgente(MSG_ERRO_TECNICO, tuple(chamadas), uso, falhou=True)
            uso = _somar(uso, r.uso)

            if r.motivo_parada == "ferramenta" and r.chamadas_ferramenta:
                if rodadas >= MAX_ITERACOES_FERRAMENTA:
                    log.warning("Limite de %d iterações de ferramenta atingido", MAX_ITERACOES_FERRAMENTA)
                    return self._fechar(base, mensagem, MSG_LIMITE, chamadas, uso, falhou=True)
                rodadas += 1
                resultados = []
                for c in r.chamadas_ferramenta:
                    resultado = self._ferramentas.executar(c.nome, c.argumentos)
                    ok = resultado.get("ok") is True
                    codigo = None if ok else (resultado.get("erro") or {}).get("codigo")
                    chamadas.append(FerramentaChamada(c.nome, dict(c.argumentos), ok, codigo))
                    resultados.append(ResultadoFerramenta(c.id, resultado, erro=not ok))
                novas += [r.como_mensagem(), Mensagem(papel="user", resultados_ferramenta=tuple(resultados))]
                continue

            texto = r.texto.strip()
            if r.motivo_parada == "max_tokens":
                if r.chamadas_ferramenta or not texto:
                    log.warning("Resposta cortada por max_tokens sem texto aproveitável")
                    return self._descartar(chamadas, uso)
                return self._fechar(base, mensagem, texto + MSG_CORTADA, chamadas, uso, novas=novas)
            if not texto:
                log.warning("Resposta vazia do modelo (motivo %s)", r.motivo_parada_bruto)
                return self._descartar(chamadas, uso)
            return self._fechar(base, mensagem, texto, chamadas, uso, novas=novas, assistente=r.como_mensagem())

    def _descartar(self, chamadas, uso) -> RespostaAgente:
        """Turno sem resposta utilizável: não entra no histórico."""
        return RespostaAgente(MSG_ERRO_TECNICO, tuple(chamadas), uso, falhou=True)

    def _fechar(
        self,
        base,
        mensagem,
        texto,
        chamadas,
        uso,
        falhou=False,
        novas=None,
        assistente=None,
    ) -> RespostaAgente:
        """Grava o turno no histórico. Em fallback/corte guarda só o par texto (sem ferramentas
        pendentes); no caso normal guarda também as idas e vindas de ferramenta."""
        if assistente is not None:
            final = [*base, *(novas or []), assistente]
        else:
            final = [*base, Mensagem(papel="assistant", texto=texto)]
        self._historico = self._janela(final)
        return RespostaAgente(texto, tuple(chamadas), uso, falhou=falhou)


def criar_agente(config: Config | None = None) -> Agente:
    """Monta Config + dados + ferramentas + provedor Anthropic. Levanta ProvedorErro sem chave."""
    config = config or Config.from_env()
    ferramentas = Ferramentas(carregar_dados(config.dados_dir))
    provedor = ProvedorAnthropic(modelo=config.modelo, api_key=config.anthropic_api_key)
    return Agente(config, provedor, ferramentas)
