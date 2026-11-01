"""Provedor Anthropic com cliente falso (sem rede)."""

import anthropic
import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from emporio_agente.provedores.anthropic import ProvedorAnthropic
from emporio_agente.provedores.base import (
    ChamadaFerramenta,
    Mensagem,
    Provedor,
    ProvedorErro,
    RespostaProvedor,
    ResultadoFerramenta,
    UsoTokens,
)

SCHEMA = {
    "name": "buscar_produtos",
    "description": "Busca produtos.",
    "input_schema": {"type": "object", "properties": {"texto": {"type": "string"}}},
}


def resposta_sdk(blocos, stop_reason="end_turn", **uso):
    return Message(
        id="msg_1",
        content=blocos,
        model="claude-haiku-5-5",
        role="assistant",
        stop_reason=stop_reason,
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=uso.pop("input_tokens", 10), output_tokens=uso.pop("output_tokens", 5), **uso),
    )


class ClienteFalso:
    def __init__(self, resposta=None, erro=None):
        self.chamadas = []
        self._resposta = resposta
        self._erro = erro
        self.messages = self

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        if self._erro:
            raise self._erro
        return self._resposta


def provedor(resposta=None, erro=None):
    cliente = ClienteFalso(resposta, erro)
    return ProvedorAnthropic(modelo="claude-haiku-5-5", cliente=cliente), cliente


def gerar(p, mensagens=None, **kw):
    return p.gerar(
        system="Você é a atendente.",
        mensagens=mensagens or [Mensagem(papel="user", texto="oi")],
        ferramentas=[SCHEMA],
        **kw,
    )


def test_atende_o_protocolo_provedor():
    p, _ = provedor(resposta_sdk([TextBlock(type="text", text="oi")]))
    assert isinstance(p, Provedor)


def test_requisicao_tem_modelo_system_com_cache_e_ferramentas():
    p, cliente = provedor(resposta_sdk([TextBlock(type="text", text="olá")]))
    gerar(p, max_tokens=300)
    req = cliente.chamadas[0]
    assert req["model"] == "claude-haiku-5-5"
    assert req["max_tokens"] == 300
    assert req["system"] == [
        {"type": "text", "text": "Você é a atendente.", "cache_control": {"type": "ephemeral"}}
    ]
    assert req["tools"] == [SCHEMA]
    assert req["messages"] == [{"role": "user", "content": "oi"}]


def test_sem_ferramentas_nao_envia_tools():
    p, cliente = provedor(resposta_sdk([TextBlock(type="text", text="olá")]))
    p.gerar(system="s", mensagens=[Mensagem(papel="user", texto="oi")], ferramentas=[])
    assert "tools" not in cliente.chamadas[0]


def test_resposta_de_texto():
    p, _ = provedor(resposta_sdk([TextBlock(type="text", text="Olá, "), TextBlock(type="text", text="tudo bem?")]))
    r = gerar(p)
    assert isinstance(r, RespostaProvedor)
    assert r.texto == "Olá, tudo bem?"
    assert r.chamadas_ferramenta == ()
    assert r.motivo_parada == "fim_turno"


def test_resposta_com_chamada_de_ferramenta():
    blocos = [
        TextBlock(type="text", text="Vou consultar."),
        ToolUseBlock(type="tool_use", id="toolu_1", name="buscar_produtos", input={"texto": "gd20"}),
    ]
    p, _ = provedor(resposta_sdk(blocos, stop_reason="tool_use"))
    r = gerar(p)
    assert r.motivo_parada == "ferramenta"
    assert r.texto == "Vou consultar."
    assert r.chamadas_ferramenta == (ChamadaFerramenta(id="toolu_1", nome="buscar_produtos", argumentos={"texto": "gd20"}),)


@pytest.mark.parametrize(
    "bruto,esperado",
    [("end_turn", "fim_turno"), ("tool_use", "ferramenta"), ("max_tokens", "max_tokens"), ("refusal", "outro"), ("pause_turn", "outro")],
)
def test_motivo_de_parada_normalizado(bruto, esperado):
    p, _ = provedor(resposta_sdk([TextBlock(type="text", text="x")], stop_reason=bruto))
    r = gerar(p)
    assert r.motivo_parada == esperado
    assert r.motivo_parada_bruto == bruto


def test_uso_de_tokens_inclui_cache():
    p, _ = provedor(
        resposta_sdk(
            [TextBlock(type="text", text="x")],
            input_tokens=7,
            output_tokens=9,
            cache_creation_input_tokens=100,
            cache_read_input_tokens=50,
        )
    )
    assert gerar(p).uso == UsoTokens(entrada=7, saida=9, cache_criacao=100, cache_leitura=50)


def test_uso_sem_campos_de_cache_vira_zero():
    p, _ = provedor(resposta_sdk([TextBlock(type="text", text="x")]))
    uso = gerar(p).uso
    assert uso.cache_criacao == 0 and uso.cache_leitura == 0


def test_historico_com_ferramenta_e_resultado_vai_no_formato_da_api():
    historico = [
        Mensagem(papel="user", texto="tem takamine gd20?"),
        Mensagem(
            papel="assistant",
            texto="Vou ver.",
            chamadas_ferramenta=(ChamadaFerramenta(id="toolu_1", nome="buscar_produtos", argumentos={"texto": "gd20"}),),
        ),
        Mensagem(
            papel="user",
            resultados_ferramenta=(
                ResultadoFerramenta(chamada_id="toolu_1", conteudo={"ok": True, "nome": "Violão Épico"}),
                ResultadoFerramenta(chamada_id="toolu_2", conteudo={"ok": False}, erro=True),
            ),
        ),
    ]
    p, cliente = provedor(resposta_sdk([TextBlock(type="text", text="x")]))
    gerar(p, mensagens=historico)
    assert cliente.chamadas[0]["messages"] == [
        {"role": "user", "content": "tem takamine gd20?"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Vou ver."},
                {"type": "tool_use", "id": "toolu_1", "name": "buscar_produtos", "input": {"texto": "gd20"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"ok": true, "nome": "Violão Épico"}'},
                {"type": "tool_result", "tool_use_id": "toolu_2", "content": '{"ok": false}', "is_error": True},
            ],
        },
    ]


def test_mensagem_do_assistente_sem_texto_nao_envia_bloco_de_texto_vazio():
    historico = [
        Mensagem(papel="user", texto="oi"),
        Mensagem(
            papel="assistant",
            chamadas_ferramenta=(ChamadaFerramenta(id="t1", nome="x", argumentos={}),),
        ),
    ]
    p, cliente = provedor(resposta_sdk([TextBlock(type="text", text="x")]))
    gerar(p, mensagens=historico)
    assert cliente.chamadas[0]["messages"][1]["content"] == [{"type": "tool_use", "id": "t1", "name": "x", "input": {}}]


def test_resposta_vira_mensagem_do_assistente_para_o_historico():
    blocos = [
        TextBlock(type="text", text="Vou ver."),
        ToolUseBlock(type="tool_use", id="toolu_1", name="buscar_produtos", input={"texto": "a"}),
    ]
    p, _ = provedor(resposta_sdk(blocos, stop_reason="tool_use"))
    msg = gerar(p).como_mensagem()
    assert msg == Mensagem(
        papel="assistant",
        texto="Vou ver.",
        chamadas_ferramenta=(ChamadaFerramenta(id="toolu_1", nome="buscar_produtos", argumentos={"texto": "a"}),),
    )


def test_erro_da_api_vira_provedor_erro():
    erro = anthropic.AnthropicError("falha de rede simulada")
    p, _ = provedor(erro=erro)
    with pytest.raises(ProvedorErro) as info:
        gerar(p)
    assert info.value.__cause__ is erro


def test_sem_chave_nem_cliente_gera_erro_claro():
    with pytest.raises(ProvedorErro, match="ANTHROPIC_API_KEY"):
        ProvedorAnthropic(modelo="claude-haiku-5-5", api_key=None)


def test_cria_cliente_real_quando_ha_chave():
    p = ProvedorAnthropic(modelo="claude-haiku-5-5", api_key="sk-ant-teste")
    assert isinstance(p, Provedor)
