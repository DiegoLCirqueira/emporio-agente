"""Provedor Gemini com cliente falso (sem rede, sem chave real)."""

import pytest
from google.genai import errors, types

from emporio_agente.ferramentas import SCHEMAS
from emporio_agente.provedores.base import (
    CHAVE_AUSENTE,
    COTA_ESGOTADA,
    ChamadaFerramenta,
    Mensagem,
    Provedor,
    ProvedorErro,
    ResultadoFerramenta,
    UsoTokens,
)
from emporio_agente.provedores.gemini import MARGEM_RACIOCINIO, ProvedorGemini

SCHEMA_BUSCA = {
    "name": "buscar_produtos",
    "description": "Busca produtos.",
    "input_schema": {
        "type": "object",
        "properties": {
            "texto": {"type": "string", "description": "Termos."},
            "preco_max": {"type": "number"},
            "so_disponiveis": {"type": "boolean"},
            "forma": {"type": "string", "enum": ["pix", "credito"]},
        },
        "required": ["texto"],
        "additionalProperties": False,
    },
}
SCHEMA_SEM_ARGS = {
    "name": "listar_promocoes_ativas",
    "description": "Lista promoções.",
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
}


def parte_texto(t, thought=False):
    return types.Part(text=t, thought=thought or None)


def parte_chamada(nome, args, id=None, assinatura=None):
    return types.Part(function_call=types.FunctionCall(name=nome, args=args, id=id), thought_signature=assinatura)


def resposta(partes, finish=types.FinishReason.STOP, **uso):
    metadados = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=uso.get("prompt", 10),
        candidates_token_count=uso.get("candidatos", 5),
        thoughts_token_count=uso.get("pensamento"),
        cached_content_token_count=uso.get("cache"),
    )
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=partes), finish_reason=finish)],
        usage_metadata=metadados,
    )


class ClienteFalso:
    def __init__(self, *roteiro):
        self.roteiro = list(roteiro)
        self.chamadas = []
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.chamadas.append({"model": model, "contents": contents, "config": config})
        item = self.roteiro.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def provedor(*roteiro, **kw):
    cliente = ClienteFalso(*roteiro)
    esperas = []
    kw.setdefault("dormir", esperas.append)
    kw.setdefault("aleatorio", lambda: 0.0)
    return ProvedorGemini(modelo="gemini-3.8-flash", cliente=cliente, **kw), cliente, esperas


def gerar(p, mensagens=None, ferramentas=(SCHEMA_BUSCA,), **kw):
    return p.gerar(system="Você é a atendente.", mensagens=mensagens or [Mensagem(papel="user", texto="oi")], ferramentas=list(ferramentas), **kw)


def erro_http(codigo, status, retry=None):
    detalhes = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry}] if retry else []
    corpo = {"error": {"code": codigo, "message": "msg", "status": status, "details": detalhes}}
    return (errors.ClientError if codigo < 500 else errors.ServerError)(codigo, corpo)


# --- requisição ------------------------------------------------------------------------


def test_atende_o_protocolo_provedor():
    p, _, _ = provedor(resposta([parte_texto("oi")]))
    assert isinstance(p, Provedor)


def test_requisicao_tem_modelo_system_e_chamada_automatica_desligada():
    p, cliente, _ = provedor(resposta([parte_texto("olá")]))
    gerar(p, max_tokens=300)
    req = cliente.chamadas[0]
    assert req["model"] == "gemini-3.8-flash"
    cfg = req["config"]
    assert cfg.system_instruction == "Você é a atendente."
    assert cfg.automatic_function_calling.disable is True  # o loop é nosso (D1)
    assert cfg.max_output_tokens == 300 + MARGEM_RACIOCINIO
    assert req["contents"][0].role == "user" and req["contents"][0].parts[0].text == "oi"


def test_schemas_neutros_viram_declaracoes_do_gemini():
    p, cliente, _ = provedor(resposta([parte_texto("x")]))
    gerar(p, ferramentas=[SCHEMA_BUSCA, SCHEMA_SEM_ARGS])
    declaracoes = cliente.chamadas[0]["config"].tools[0].function_declarations
    busca, sem_args = declaracoes
    assert busca.name == "buscar_produtos" and busca.description == "Busca produtos."
    props = busca.parameters.properties
    assert busca.parameters.type == types.Type.OBJECT
    assert props["texto"].type == types.Type.STRING and props["texto"].description == "Termos."
    assert props["preco_max"].type == types.Type.NUMBER
    assert props["so_disponiveis"].type == types.Type.BOOLEAN
    assert props["forma"].enum == ["pix", "credito"]
    assert busca.parameters.required == ["texto"]
    # objeto sem propriedades: o Gemini rejeita, então a declaração vai sem parâmetros
    assert sem_args.name == "listar_promocoes_ativas" and sem_args.parameters is None


def test_todos_os_schemas_reais_das_ferramentas_sao_convertidos():
    p, cliente, _ = provedor(resposta([parte_texto("x")]))
    gerar(p, ferramentas=SCHEMAS)
    nomes = [d.name for d in cliente.chamadas[0]["config"].tools[0].function_declarations]
    assert nomes == [s["name"] for s in SCHEMAS]


def test_sem_ferramentas_nao_envia_tools():
    p, cliente, _ = provedor(resposta([parte_texto("x")]))
    gerar(p, ferramentas=[])
    assert not cliente.chamadas[0]["config"].tools


# --- resposta --------------------------------------------------------------------------


def test_resposta_de_texto_ignora_partes_de_pensamento():
    p, _, _ = provedor(resposta([parte_texto("pensando...", thought=True), parte_texto("Olá, "), parte_texto("tudo bem?")]))
    r = gerar(p)
    assert r.texto == "Olá, tudo bem?"
    assert r.chamadas_ferramenta == () and r.motivo_parada == "fim_turno"


def test_chamada_de_ferramenta_com_id_gerado_e_estavel():
    p, _, _ = provedor(
        resposta([parte_texto("Vou ver."), parte_chamada("buscar_produtos", {"texto": "gd20"}), parte_chamada("listar_promocoes_ativas", {})]),
        resposta([parte_chamada("buscar_produtos", {"texto": "x"})]),
    )
    r = gerar(p)
    assert r.motivo_parada == "ferramenta" and r.texto == "Vou ver."
    a, b = r.chamadas_ferramenta
    assert (a.nome, a.argumentos) == ("buscar_produtos", {"texto": "gd20"})
    assert b.nome == "listar_promocoes_ativas" and b.argumentos == {}
    assert a.id and b.id and a.id != b.id
    outra = gerar(p).chamadas_ferramenta[0]
    assert outra.id not in (a.id, b.id)  # ids únicos ao longo da sessão


def test_id_devolvido_pela_api_e_respeitado():
    p, _, _ = provedor(resposta([parte_chamada("buscar_produtos", {"texto": "a"}, id="abc123")]))
    assert gerar(p).chamadas_ferramenta[0].id == "abc123"


@pytest.mark.parametrize(
    "finish,esperado",
    [
        (types.FinishReason.STOP, "fim_turno"),
        (types.FinishReason.MAX_TOKENS, "max_tokens"),
        (types.FinishReason.SAFETY, "outro"),
        (types.FinishReason.MALFORMED_FUNCTION_CALL, "outro"),
    ],
)
def test_motivo_de_parada_normalizado(finish, esperado):
    p, _, _ = provedor(resposta([parte_texto("x")], finish=finish))
    r = gerar(p)
    assert r.motivo_parada == esperado
    assert r.motivo_parada_bruto == finish.name


def test_uso_de_tokens():
    p, _, _ = provedor(resposta([parte_texto("x")], prompt=100, candidatos=20, pensamento=30, cache=40))
    assert gerar(p).uso == UsoTokens(entrada=100, saida=50, cache_criacao=0, cache_leitura=40)


def test_uso_ausente_vira_zero():
    p, _, _ = provedor(types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[parte_texto("x")]), finish_reason=types.FinishReason.STOP)]))
    assert gerar(p).uso == UsoTokens()


def test_resposta_bloqueada_sem_candidatos_vira_vazia_e_outro():
    p, _, _ = provedor(types.GenerateContentResponse(candidates=None))
    r = gerar(p)
    assert r.texto == "" and r.chamadas_ferramenta == () and r.motivo_parada == "outro"


# --- histórico -------------------------------------------------------------------------


def test_historico_com_chamada_e_resultado_vai_no_formato_do_gemini():
    p, cliente, _ = provedor(
        resposta([parte_chamada("buscar_produtos", {"texto": "gd20"}), parte_chamada("listar_promocoes_ativas", {})]),
        resposta([parte_texto("Temos.")]),
    )
    r1 = gerar(p, ferramentas=[SCHEMA_BUSCA, SCHEMA_SEM_ARGS])
    a, b = r1.chamadas_ferramenta
    historico = [
        Mensagem(papel="user", texto="tem gd20?"),
        r1.como_mensagem(),
        Mensagem(
            papel="user",
            resultados_ferramenta=(
                ResultadoFerramenta(a.id, {"ok": True, "produtos": [1]}),
                ResultadoFerramenta(b.id, {"ok": False, "erro": {"codigo": "X"}}, erro=True),
            ),
        ),
    ]
    gerar(p, mensagens=historico, ferramentas=[SCHEMA_BUSCA, SCHEMA_SEM_ARGS])
    contents = cliente.chamadas[1]["contents"]
    assert [c.role for c in contents] == ["user", "model", "user"]
    chamadas = [pt.function_call for pt in contents[1].parts]
    assert [(c.name, c.args) for c in chamadas] == [("buscar_produtos", {"texto": "gd20"}), ("listar_promocoes_ativas", {})]
    respostas = [pt.function_response for pt in contents[2].parts]
    assert [(f.name, f.response) for f in respostas] == [
        ("buscar_produtos", {"ok": True, "produtos": [1]}),
        ("listar_promocoes_ativas", {"ok": False, "erro": {"codigo": "X"}}),
    ]


def test_assinatura_de_pensamento_e_devolvida_com_a_chamada():
    p, cliente, _ = provedor(
        resposta([parte_chamada("buscar_produtos", {"texto": "a"}, assinatura=b"assinatura-opaca")]),
        resposta([parte_texto("ok")]),
    )
    r1 = gerar(p)
    historico = [
        Mensagem(papel="user", texto="oi"),
        r1.como_mensagem(),
        Mensagem(papel="user", resultados_ferramenta=(ResultadoFerramenta(r1.chamadas_ferramenta[0].id, {"ok": True}),)),
    ]
    gerar(p, mensagens=historico)
    parte = cliente.chamadas[1]["contents"][1].parts[0]
    assert parte.thought_signature == b"assinatura-opaca"
    assert parte.function_call.name == "buscar_produtos"


def test_chamada_sem_assinatura_conhecida_e_reconstruida():
    p, cliente, _ = provedor(resposta([parte_texto("ok")]))
    historico = [
        Mensagem(papel="user", texto="oi"),
        Mensagem(papel="assistant", chamadas_ferramenta=(ChamadaFerramenta("zz", "buscar_produtos", {"texto": "a"}),)),
        Mensagem(papel="user", resultados_ferramenta=(ResultadoFerramenta("zz", {"ok": True}),)),
    ]
    gerar(p, mensagens=historico)
    contents = cliente.chamadas[0]["contents"]
    assert contents[1].parts[0].function_call.name == "buscar_produtos"
    assert contents[2].parts[0].function_response.name == "buscar_produtos"


def test_texto_do_assistente_antes_da_chamada():
    p, cliente, _ = provedor(resposta([parte_texto("ok")]))
    historico = [
        Mensagem(papel="user", texto="oi"),
        Mensagem(papel="assistant", texto="Vou ver.", chamadas_ferramenta=(ChamadaFerramenta("q", "buscar_produtos", {}),)),
        Mensagem(papel="user", resultados_ferramenta=(ResultadoFerramenta("q", {"ok": True}),)),
        Mensagem(papel="assistant", texto="Pronto."),
    ]
    gerar(p, mensagens=historico + [Mensagem(papel="user", texto="valeu")])
    contents = cliente.chamadas[0]["contents"]
    assert [pt.text for pt in contents[1].parts[:1]] == ["Vou ver."]
    assert contents[1].parts[1].function_call.name == "buscar_produtos"
    assert contents[3].role == "model" and contents[3].parts[0].text == "Pronto."


# --- limite de uso (429) e instabilidade (5xx) -----------------------------------------


def test_429_e_tentado_de_novo_com_espera_exponencial():
    p, cliente, esperas = provedor(erro_http(429, "RESOURCE_EXHAUSTED"), erro_http(429, "RESOURCE_EXHAUSTED"), resposta([parte_texto("ok")]))
    assert gerar(p).texto == "ok"
    assert len(cliente.chamadas) == 3
    assert esperas == [2.0, 4.0]


def test_jitter_e_somado_a_espera():
    p, _, esperas = provedor(erro_http(429, "RESOURCE_EXHAUSTED"), resposta([parte_texto("ok")]), aleatorio=lambda: 0.5)
    gerar(p)
    assert esperas == [2.5]


def test_respeita_retry_delay_do_erro():
    p, _, esperas = provedor(erro_http(429, "RESOURCE_EXHAUSTED", retry="7s"), resposta([parte_texto("ok")]))
    gerar(p)
    assert esperas == [7.0]


def test_cota_esgotada_depois_de_4_tentativas():
    p, cliente, esperas = provedor(*[erro_http(429, "RESOURCE_EXHAUSTED")] * 4)
    with pytest.raises(ProvedorErro) as info:
        gerar(p)
    assert info.value.codigo == COTA_ESGOTADA
    assert len(cliente.chamadas) == 4
    assert esperas == [2.0, 4.0, 8.0]


def test_retry_delay_muito_longo_nao_espera_e_ja_e_cota_esgotada():
    p, cliente, esperas = provedor(erro_http(429, "RESOURCE_EXHAUSTED", retry="3600s"))
    with pytest.raises(ProvedorErro) as info:
        gerar(p)
    assert info.value.codigo == COTA_ESGOTADA
    assert len(cliente.chamadas) == 1 and esperas == []


def test_503_tambem_e_tentado_de_novo_mas_nao_vira_cota():
    p, _, esperas = provedor(erro_http(503, "UNAVAILABLE"), resposta([parte_texto("ok")]))
    assert gerar(p).texto == "ok" and esperas == [2.0]
    p, cliente, _ = provedor(*[erro_http(503, "UNAVAILABLE")] * 4)
    with pytest.raises(ProvedorErro) as info:
        gerar(p)
    assert info.value.codigo is None and len(cliente.chamadas) == 4


def test_erro_400_nao_tenta_de_novo():
    p, cliente, esperas = provedor(erro_http(400, "INVALID_ARGUMENT"))
    with pytest.raises(ProvedorErro) as info:
        gerar(p)
    assert len(cliente.chamadas) == 1 and esperas == []
    assert "400" in str(info.value) and info.value.codigo is None


def test_erro_inesperado_do_sdk_vira_provedor_erro():
    p, _, _ = provedor(RuntimeError("conexão caiu"))
    with pytest.raises(ProvedorErro) as info:
        gerar(p)
    assert isinstance(info.value.__cause__, RuntimeError)


# --- chave -----------------------------------------------------------------------------


def test_sem_chave_nem_cliente_gera_erro_claro():
    with pytest.raises(ProvedorErro, match="GEMINI_API_KEY") as info:
        ProvedorGemini(modelo="gemini-3.8-flash", api_key=None)
    assert info.value.codigo == CHAVE_AUSENTE


def test_cria_cliente_real_quando_ha_chave_sem_expor_o_valor():
    p = ProvedorGemini(modelo="gemini-3.8-flash", api_key="chave-falsa-de-teste")
    assert isinstance(p, Provedor)
    assert "chave-falsa-de-teste" not in repr(p)
