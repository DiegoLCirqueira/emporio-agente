"""Provedor Anthropic (Messages API, SDK anthropic)."""

import json
from collections.abc import Sequence
from typing import Any

import anthropic

from emporio_agente.provedores.base import (
    ChamadaFerramenta,
    Mensagem,
    MotivoParada,
    ProvedorErro,
    RespostaProvedor,
    UsoTokens,
)

_MOTIVOS: dict[str, MotivoParada] = {
    "end_turn": "fim_turno",
    "tool_use": "ferramenta",
    "max_tokens": "max_tokens",
}


class ProvedorAnthropic:
    def __init__(self, modelo: str, api_key: str | None = None, cliente: Any = None):
        if cliente is None:
            if not api_key:
                raise ProvedorErro("ANTHROPIC_API_KEY não definida: configure a chave no .env ou no ambiente.")
            cliente = anthropic.Anthropic(api_key=api_key)
        self._cliente = cliente
        self._modelo = modelo

    def gerar(
        self,
        *,
        system: str,
        mensagens: Sequence[Mensagem],
        ferramentas: Sequence[dict],
        max_tokens: int = 1024,
    ) -> RespostaProvedor:
        requisicao: dict[str, Any] = {
            "model": self._modelo,
            "max_tokens": max_tokens,
            # cache_control no system: o prefixo (ferramentas + system) é reaproveitado entre turnos.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [_para_api(m) for m in mensagens],
        }
        if ferramentas:
            requisicao["tools"] = [dict(f) for f in ferramentas]
        try:
            resposta = self._cliente.messages.create(**requisicao)
        except anthropic.AnthropicError as e:
            raise ProvedorErro(f"Falha ao chamar a API da Anthropic: {type(e).__name__}") from e
        return _de_api(resposta)


def _para_api(m: Mensagem) -> dict[str, Any]:
    if not m.chamadas_ferramenta and not m.resultados_ferramenta:
        return {"role": m.papel, "content": m.texto}
    blocos: list[dict[str, Any]] = []
    # tool_result precisa vir antes de qualquer texto na mensagem do usuário.
    for r in m.resultados_ferramenta:
        bloco: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": r.chamada_id,
            "content": json.dumps(r.conteudo, ensure_ascii=False),
        }
        if r.erro:
            bloco["is_error"] = True
        blocos.append(bloco)
    if m.texto:
        blocos.append({"type": "text", "text": m.texto})
    for c in m.chamadas_ferramenta:
        blocos.append({"type": "tool_use", "id": c.id, "name": c.nome, "input": c.argumentos})
    # Em mensagens do assistente o texto vem antes das chamadas.
    if m.papel == "assistant" and m.texto:
        blocos.insert(0, blocos.pop(len(m.resultados_ferramenta)))
    return {"role": m.papel, "content": blocos}


def _de_api(resposta: Any) -> RespostaProvedor:
    textos: list[str] = []
    chamadas: list[ChamadaFerramenta] = []
    for bloco in resposta.content:
        if bloco.type == "text":
            textos.append(bloco.text)
        elif bloco.type == "tool_use":
            chamadas.append(ChamadaFerramenta(id=bloco.id, nome=bloco.name, argumentos=dict(bloco.input)))
    uso = resposta.usage
    return RespostaProvedor(
        texto="".join(textos),
        chamadas_ferramenta=tuple(chamadas),
        motivo_parada=_MOTIVOS.get(resposta.stop_reason, "outro"),
        uso=UsoTokens(
            entrada=uso.input_tokens or 0,
            saida=uso.output_tokens or 0,
            cache_criacao=getattr(uso, "cache_creation_input_tokens", 0) or 0,
            cache_leitura=getattr(uso, "cache_read_input_tokens", 0) or 0,
        ),
        motivo_parada_bruto=resposta.stop_reason,
    )
