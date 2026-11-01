"""Provedor Gemini (Google AI Studio, SDK google-genai, API generate_content)."""

import logging
import random
import re
import time
from collections.abc import Callable, Sequence
from typing import Any

from google import genai
from google.genai import errors, types

from emporio_agente.provedores.base import (
    CHAVE_AUSENTE,
    COTA_ESGOTADA,
    ChamadaFerramenta,
    Mensagem,
    MotivoParada,
    ProvedorErro,
    RespostaProvedor,
    UsoTokens,
)

log = logging.getLogger(__name__)

TENTATIVAS = 4
ESPERA_BASE_S = 2.0
LIMITE_ESPERA_S = 60.0  # retryDelay acima disso (ex.: cota diária) não vale esperar
TIMEOUT_MS = 60_000
# O Gemini 3 conta os tokens de raciocínio dentro de max_output_tokens: sem folga, a resposta
# pode ser cortada antes de começar.
MARGEM_RACIOCINIO = 2048
STATUS_REPETIVEIS = {500, 502, 503, 504}
CAMPOS_SCHEMA = {"type", "description", "enum", "properties", "required", "items", "format", "nullable", "minimum", "maximum"}


class ProvedorGemini:
    def __init__(
        self,
        modelo: str,
        api_key: str | None = None,
        cliente: Any = None,
        *,
        tentativas: int = TENTATIVAS,
        espera_base: float = ESPERA_BASE_S,
        dormir: Callable[[float], None] = time.sleep,
        aleatorio: Callable[[], float] = random.random,
    ):
        if cliente is None:
            if not api_key:
                raise ProvedorErro(
                    "GEMINI_API_KEY não definida: configure a chave no .env ou no ambiente.", codigo=CHAVE_AUSENTE
                )
            cliente = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
        self._cliente = cliente
        self._modelo = modelo
        self._tentativas = tentativas
        self._espera_base = espera_base
        self._dormir = dormir
        self._aleatorio = aleatorio
        self._sequencia = 0
        # Partes originais das chamadas de função, por id: preservam a thought_signature,
        # que o Gemini 3 exige de volta junto com a chamada.
        self._partes: dict[str, types.Part] = {}

    # --- API pública -------------------------------------------------------------------

    def gerar(
        self,
        *,
        system: str,
        mensagens: Sequence[Mensagem],
        ferramentas: Sequence[dict],
        max_tokens: int = 1024,
    ) -> RespostaProvedor:
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens + MARGEM_RACIOCINIO,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tools=[types.Tool(function_declarations=[_declaracao(f) for f in ferramentas])] if ferramentas else None,
        )
        resposta = self._chamar(contents=self._conteudos(mensagens), config=config)
        return self._interpretar(resposta)

    # --- chamada com repetição ---------------------------------------------------------

    def _chamar(self, *, contents, config):
        for tentativa in range(1, self._tentativas + 1):
            try:
                return self._cliente.models.generate_content(model=self._modelo, contents=contents, config=config)
            except ProvedorErro:
                raise
            except errors.APIError as e:
                espera = self._decidir_espera(e, tentativa)
                log.warning("Gemini HTTP %s (%s), tentativa %d/%d", e.code, e.status, tentativa, self._tentativas)
                self._dormir(espera)
            except Exception as e:
                raise ProvedorErro(f"Falha ao chamar a API do Gemini: {type(e).__name__}") from e
        raise AssertionError("inalcançável")  # pragma: no cover

    def _decidir_espera(self, e: errors.APIError, tentativa: int) -> float:
        """Devolve quanto esperar antes de repetir, ou levanta ProvedorErro se não vale repetir."""
        if e.code == 429:
            sugerida = _retry_delay(e)
            if sugerida is not None and sugerida > LIMITE_ESPERA_S:
                raise ProvedorErro(
                    f"Cota da API do Gemini esgotada (HTTP 429, retryDelay {sugerida:.0f}s).", codigo=COTA_ESGOTADA
                ) from e
            if tentativa >= self._tentativas:
                raise ProvedorErro("Cota da API do Gemini esgotada (HTTP 429).", codigo=COTA_ESGOTADA) from e
        elif e.code in STATUS_REPETIVEIS:
            if tentativa >= self._tentativas:
                raise ProvedorErro(f"API do Gemini indisponível (HTTP {e.code}, {e.status}).") from e
            sugerida = None
        else:
            raise ProvedorErro(f"A API do Gemini recusou a requisição (HTTP {e.code}, {e.status}).") from e
        base = sugerida if sugerida is not None else self._espera_base * 2 ** (tentativa - 1)
        return base + self._aleatorio()

    # --- conversão de entrada ----------------------------------------------------------

    def _conteudos(self, mensagens: Sequence[Mensagem]) -> list[types.Content]:
        nomes = {c.id: c.nome for m in mensagens for c in m.chamadas_ferramenta}
        conteudos = []
        for m in mensagens:
            partes: list[types.Part] = []
            for r in m.resultados_ferramenta:
                original = self._partes.get(r.chamada_id)
                id_api = original.function_call.id if original is not None else None
                partes.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=id_api, name=nomes.get(r.chamada_id, "desconhecida"), response=r.conteudo
                        )
                    )
                )
            if m.texto:
                partes.append(types.Part(text=m.texto))
            for c in m.chamadas_ferramenta:
                partes.append(
                    self._partes.get(c.id)
                    or types.Part(function_call=types.FunctionCall(name=c.nome, args=c.argumentos))
                )
            conteudos.append(types.Content(role="user" if m.papel == "user" else "model", parts=partes))
        return conteudos

    # --- conversão de saída ------------------------------------------------------------

    def _interpretar(self, resposta: types.GenerateContentResponse) -> RespostaProvedor:
        uso = _uso(resposta.usage_metadata)
        candidatos = resposta.candidates or []
        if not candidatos or candidatos[0].content is None:
            bloqueio = getattr(resposta.prompt_feedback, "block_reason", None)
            return RespostaProvedor("", (), "outro", uso, motivo_parada_bruto=bloqueio.name if bloqueio else None)
        candidato = candidatos[0]
        textos: list[str] = []
        chamadas: list[ChamadaFerramenta] = []
        for parte in candidato.content.parts or []:
            if parte.function_call is not None:
                self._sequencia += 1
                chamada_id = parte.function_call.id or f"gemini-{self._sequencia}-{parte.function_call.name}"
                self._partes[chamada_id] = parte
                chamadas.append(
                    ChamadaFerramenta(chamada_id, parte.function_call.name, dict(parte.function_call.args or {}))
                )
            elif parte.text and not parte.thought:
                textos.append(parte.text)
        finish = candidato.finish_reason
        motivo: MotivoParada
        if chamadas:
            motivo = "ferramenta"
        elif finish in (None, types.FinishReason.STOP):
            motivo = "fim_turno"
        elif finish == types.FinishReason.MAX_TOKENS:
            motivo = "max_tokens"
        else:
            motivo = "outro"
        return RespostaProvedor(
            texto="".join(textos),
            chamadas_ferramenta=tuple(chamadas),
            motivo_parada=motivo,
            uso=uso,
            motivo_parada_bruto=finish.name if finish else None,
        )


def _uso(meta: types.GenerateContentResponseUsageMetadata | None) -> UsoTokens:
    if meta is None:
        return UsoTokens()
    return UsoTokens(
        entrada=meta.prompt_token_count or 0,
        saida=(meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0),
        cache_criacao=0,
        cache_leitura=meta.cached_content_token_count or 0,
    )


def _retry_delay(e: errors.APIError) -> float | None:
    """Lê o retryDelay sugerido pela API (RetryInfo em details ou 'retry in Xs' na mensagem)."""
    corpo = e.details if isinstance(e.details, dict) else {}
    for item in (corpo.get("error") or {}).get("details") or []:
        valor = item.get("retryDelay") if isinstance(item, dict) else None
        if isinstance(valor, str) and re.fullmatch(r"\d+(\.\d+)?s", valor):
            return float(valor[:-1])
    achado = re.search(r"retry in (\d+(?:\.\d+)?)s", str(e.message or ""), re.IGNORECASE)
    return float(achado.group(1)) if achado else None


def _declaracao(ferramenta: dict) -> types.FunctionDeclaration:
    parametros = _schema(ferramenta["input_schema"])
    if parametros is not None and parametros.get("type") == "object" and not parametros.get("properties"):
        parametros = None  # objeto sem propriedades é rejeitado pelo Gemini
    return types.FunctionDeclaration(
        name=ferramenta["name"], description=ferramenta["description"], parameters=parametros
    )


def _schema(schema: dict) -> dict:
    """JSON Schema neutro -> subconjunto aceito pelo Gemini (descarta additionalProperties etc.)."""
    saida: dict[str, Any] = {}
    for chave, valor in schema.items():
        if chave not in CAMPOS_SCHEMA:
            continue
        if chave == "properties":
            saida[chave] = {nome: _schema(sub) for nome, sub in valor.items()}
        elif chave == "items":
            saida[chave] = _schema(valor)
        else:
            saida[chave] = valor
    return saida
