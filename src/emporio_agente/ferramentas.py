"""Ferramentas (function calling) do agente: consultas sobre os dados da loja.

Todas são somente leitura. O despachante `Ferramentas.executar` nunca levanta exceção:
devolve sempre um dict com "ok": True/False.
"""

import difflib
import logging
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from emporio_agente.dados import Dados, Produto

log = logging.getLogger(__name__)

CENTAVOS = Decimal("0.01")
DESCONTO_PIX = Decimal("0.05")
LIMITE_RESULTADOS = 10
LIMITE_AMBIGUIDADE = 5

STOPWORDS = {
    "de", "da", "do", "das", "dos", "para", "pra", "pro", "um", "uma", "o", "a", "os", "as",
    "com", "e", "em", "no", "na", "nos", "nas", "que", "quero", "queria", "gostaria", "tem",
    "voces", "preco", "valor", "quanto", "custa", "comprar", "procuro", "algum", "alguma",
}  # fmt: skip

ACESSORIOS = {
    "corda", "cordas", "encordoamento", "palheta", "palhetas", "capa", "capas", "cabo", "cabos",
    "correia", "correias", "afinador", "estojo", "case", "pedal", "pedais", "baqueta", "baquetas",
    "microfone", "suporte", "metronomo", "capotraste", "banqueta", "amplificador",
}  # fmt: skip

DISPONIBILIDADE = {
    "disponivel": "Disponível",
    "esgotado": "Esgotado no momento",
    "em_breve": "Em breve (ainda não disponível para compra)",
    "descontinuado": "Descontinuado (fora de linha)",
}


class ErroFerramenta(Exception):
    def __init__(self, codigo: str, mensagem: str):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem


# --- utilidades ------------------------------------------------------------------------


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def formatar_brl(valor: Decimal) -> str:
    q = arredondar(valor)
    sinal = "-" if q < 0 else ""
    inteiro, decimais = f"{abs(q):.2f}".split(".")
    return f"{sinal}R$ {int(inteiro):,}".replace(",", ".") + f",{decimais}"


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


def _radical(token: str) -> str:
    """Singulariza de forma simples: violões/violoes -> violao, guitarras -> guitarra."""
    if token.endswith(("oes", "aes")) and len(token) > 4:
        return token[:-3] + "ao"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _tokens(texto: str) -> list[str]:
    return [_radical(t) for t in normalizar(texto).split()]


def _com_concatenacoes(tokens: list[str]) -> set[str]:
    """Conjunto de tokens mais as junções de vizinhos ("gd" "20" -> "gd20")."""
    resultado = set(tokens)
    for i in range(len(tokens)):
        for tam in (2, 3):
            if i + tam <= len(tokens):
                resultado.add("".join(tokens[i : i + tam]))
    return resultado


def _casa(token: str, haystack: set[str], prefixo: bool = True) -> bool:
    if token in haystack:
        return True
    return prefixo and len(token) >= 3 and any(h.startswith(token) for h in haystack)


def _cobre(consulta: list[str], haystack: set[str], prefixo: bool = True) -> bool:
    """True se todos os tokens da consulta (ou junções de vizinhos) estão no haystack.
    Com prefixo=False exige igualdade de token (D-28 não casa com D-28E)."""
    i = 0
    while i < len(consulta):
        for tam in (3, 2):
            if i + tam <= len(consulta) and "".join(consulta[i : i + tam]) in haystack:
                i += tam
                break
        else:
            if not _casa(consulta[i], haystack, prefixo):
                return False
            i += 1
    return True


def _numero(valor: Any) -> Decimal:
    if isinstance(valor, bool):
        raise ValueError
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    texto = str(valor).replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return Decimal(texto)


def _coagir(nome: str, valor: Any, tipo: str) -> Any:
    try:
        if tipo == "string":
            if not isinstance(valor, str):
                raise ValueError
            return valor.strip() or None
        if tipo == "integer":
            if isinstance(valor, bool):
                raise ValueError
            if isinstance(valor, int):
                return valor
            if isinstance(valor, str) and valor.strip().isdigit():
                return int(valor.strip())
            raise ValueError
        if tipo == "number":
            return _numero(valor)
        if tipo == "boolean":
            if isinstance(valor, bool):
                return valor
            if isinstance(valor, str) and valor.strip().lower() in ("true", "false"):
                return valor.strip().lower() == "true"
            raise ValueError
    except (ValueError, InvalidOperation):
        raise ErroFerramenta(
            "ARGUMENTO_INVALIDO", f"O argumento '{nome}' deve ser do tipo {tipo}."
        ) from None
    raise ErroFerramenta("ARGUMENTO_INVALIDO", f"Tipo desconhecido para '{nome}'.")


# --- schemas (neutros de provedor) -----------------------------------------------------

SCHEMAS: list[dict] = [
    {
        "name": "buscar_produtos",
        "description": (
            "Busca produtos no catálogo da loja por texto livre (nome, marca, modelo, tipo), "
            "categoria e/ou faixa de preço. Use SEMPRE que o cliente perguntar se a loja tem "
            "um produto, quiser opções, preços ou disponibilidade. Tolera acentos, maiúsculas e "
            "variações como 'gd 20' ou 'gd20'. Se a resposta vier com 'ambiguo': true, pergunte "
            "ao cliente qual dos 'candidatos' ele quer antes de afirmar preço ou estoque. Se vier "
            "'possivel_acessorio': true, a loja não vende acessórios: siga a regra de acessórios."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "Termos de busca, ex.: 'takamine gd20', 'violão nylon'."},
                "categoria": {
                    "type": "string",
                    "description": "Nome da categoria, ex.: 'Violões', 'Ukuleles', 'Guitarras'.",
                },
                "preco_min": {"type": "number", "description": "Preço mínimo em reais (opcional)."},
                "preco_max": {"type": "number", "description": "Preço máximo em reais (opcional)."},
                "so_disponiveis": {
                    "type": "boolean",
                    "description": "Padrão true: lista só o que pode ser comprado agora. Use false para incluir esgotados, em breve e descontinuados.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "detalhar_produto",
        "description": (
            "Devolve os detalhes de UM produto (descrição, especificações, preço, promoção ativa, "
            "preço no PIX e disponibilidade). Use quando o cliente já escolheu um produto ou pedir "
            "ficha técnica. Informe product_id (quando conhecido de uma busca anterior) ou o nome."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "description": "Identificador do produto."},
                "nome": {"type": "string", "description": "Nome ou parte do nome do produto."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "listar_promocoes_ativas",
        "description": (
            "Lista as promoções que estão valendo agora, com preço de tabela e preço promocional. "
            "Use quando o cliente perguntar por promoções, ofertas ou descontos. Só o que esta "
            "ferramenta devolve existe: nunca prometa desconto que ela não listou."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


# --- implementação ---------------------------------------------------------------------


class Ferramentas:
    def __init__(self, dados: Dados):
        self._dados = dados
        self._promocao_ativa = {}
        for promo in dados.promocoes:
            if promo.ativa:
                atual = self._promocao_ativa.get(promo.product_id)
                if atual is None or promo.desconto_percent > atual.desconto_percent:
                    self._promocao_ativa[promo.product_id] = promo
        self._indice = {}
        vocabulario: set[str] = set()
        for p in dados.produtos:
            nome = _tokens(p.nome)
            categoria = _tokens(dados.categoria(p.category_id).nome)
            descricao = _tokens(p.descricao)
            self._indice[p.product_id] = (
                _com_concatenacoes(nome),
                _com_concatenacoes(nome + categoria),
                _com_concatenacoes(nome + categoria + descricao),
            )
            vocabulario.update(nome + categoria)
        self._vocabulario = sorted(vocabulario)
        self._categorias_tokens = {
            c.category_id: _com_concatenacoes(_tokens(c.nome)) for c in dados.categorias
        }

    @property
    def schemas(self) -> list[dict]:
        return [dict(s) for s in SCHEMAS]

    # despachante ---------------------------------------------------------------------

    def executar(self, nome: str, argumentos: Any = None) -> dict:
        """Executa a ferramenta `nome`. Nunca levanta exceção."""
        try:
            schema = next((s for s in SCHEMAS if s["name"] == nome), None)
            if schema is None:
                raise ErroFerramenta("FERRAMENTA_DESCONHECIDA", f"A ferramenta '{nome}' não existe.")
            kwargs = self._validar(schema["input_schema"], argumentos)
            return {"ok": True, **getattr(self, nome)(**kwargs)}
        except ErroFerramenta as e:
            return {"ok": False, "erro": {"codigo": e.codigo, "mensagem": e.mensagem}}
        except Exception:
            log.exception("Erro interno na ferramenta %s", nome)
            return {
                "ok": False,
                "erro": {"codigo": "ERRO_INTERNO", "mensagem": "Não foi possível concluir a consulta agora."},
            }

    @staticmethod
    def _validar(schema: dict, argumentos: Any) -> dict:
        if argumentos is None:
            argumentos = {}
        if not isinstance(argumentos, dict):
            raise ErroFerramenta("ARGUMENTO_INVALIDO", "Os argumentos devem ser um objeto JSON.")
        props = schema["properties"]
        desconhecidos = sorted(set(argumentos) - set(props))
        if desconhecidos:
            raise ErroFerramenta("ARGUMENTO_INVALIDO", f"Argumentos desconhecidos: {', '.join(desconhecidos)}.")
        resultado = {}
        for chave, valor in argumentos.items():
            if valor is None:
                continue
            coagido = _coagir(chave, valor, props[chave]["type"])
            if coagido is not None:
                resultado[chave] = coagido
        faltando = [r for r in schema.get("required", []) if r not in resultado]
        if faltando:
            raise ErroFerramenta("ARGUMENTO_INVALIDO", f"Argumentos obrigatórios ausentes: {', '.join(faltando)}.")
        return resultado

    # produtos ------------------------------------------------------------------------

    @staticmethod
    def _codigo_disponibilidade(p: Produto) -> str:
        if p.status == "active":
            return "disponivel" if p.estoque > 0 else "esgotado"
        if p.status == "coming_soon":
            return "em_breve"
        return "descontinuado"

    def _visao(self, p: Produto, detalhado: bool = False) -> dict:
        codigo = self._codigo_disponibilidade(p)
        visao: dict[str, Any] = {
            "product_id": p.product_id,
            "nome": p.nome,
            "categoria": self._dados.categoria(p.category_id).nome,
            "preco_tabela": formatar_brl(p.preco),
            "disponibilidade": {"codigo": codigo, "rotulo": DISPONIBILIDADE[codigo]},
        }
        promo = self._promocao_ativa.get(p.product_id)
        if promo:
            visao["promocao"] = {"desconto_percent": promo.desconto_percent, "descricao": promo.descricao}
            visao["preco_promocional"] = formatar_brl(self._preco_promocional(p, promo.desconto_percent))
            visao["observacao_pix"] = (
                "O desconto de 5% do PIX não se soma à promoção: vale o preço promocional em qualquer forma de pagamento."
            )
        else:
            visao["preco_pix"] = formatar_brl(arredondar(p.preco * (1 - DESCONTO_PIX)))
        if detalhado:
            visao["descricao"] = p.descricao
            visao["especificacoes"] = p.specs
        return visao

    @staticmethod
    def _preco_promocional(p: Produto, desconto_percent: int) -> Decimal:
        return arredondar(p.preco * (Decimal(100) - desconto_percent) / 100)

    def _categorias_da_consulta(self, texto: str) -> set[int]:
        consulta = [t for t in _tokens(texto) if t not in STOPWORDS]
        if not consulta:
            return set()
        return {cid for cid, hay in self._categorias_tokens.items() if _cobre(consulta, hay)}

    def _correspondencias(self, consulta: list[str]) -> tuple[int, list[Produto]]:
        """(melhor_nivel, produtos) onde nível 3 = cobertura pelo nome, 2 = nome+categoria,
        1 = nome+categoria+descrição. Só devolve os produtos do melhor nível encontrado."""
        por_nivel: dict[int, list[Produto]] = {3: [], 2: [], 1: []}
        exatos: dict[int, list[Produto]] = {3: [], 2: [], 1: []}
        for p in self._dados.produtos:
            for nivel, hay in zip((3, 2, 1), self._indice[p.product_id]):
                if _cobre(consulta, hay):
                    por_nivel[nivel].append(p)
                    if _cobre(consulta, hay, prefixo=False):
                        exatos[nivel].append(p)
                    break
        for nivel in (3, 2, 1):
            if por_nivel[nivel]:
                return nivel, exatos[nivel] or por_nivel[nivel]
        return 0, []

    def _corrigir(self, consulta: list[str]) -> list[str]:
        corrigida = []
        for token in consulta:
            if token in self._vocabulario or len(token) < 4:
                corrigida.append(token)
                continue
            proximos = difflib.get_close_matches(token, self._vocabulario, n=1, cutoff=0.75)
            corrigida.append(proximos[0] if proximos else token)
        return corrigida

    def buscar_produtos(
        self,
        texto: str | None = None,
        categoria: str | None = None,
        preco_min: Decimal | None = None,
        preco_max: Decimal | None = None,
        so_disponiveis: bool = True,
    ) -> dict:
        if not any((texto, categoria, preco_min is not None, preco_max is not None)):
            raise ErroFerramenta(
                "ARGUMENTO_INVALIDO", "Informe ao menos texto, categoria ou faixa de preço para buscar."
            )
        base = list(self._dados.produtos)
        resposta: dict[str, Any] = {}

        if categoria:
            ids_categoria = self._categorias_da_consulta(categoria)
            base = [p for p in base if p.category_id in ids_categoria]
            if not base:
                com_produtos = {p.category_id for p in self._dados.produtos}
                nomes = [c.nome for c in self._dados.categorias if c.category_id in com_produtos]
                return {
                    "ambiguo": False,
                    "produtos": [],
                    "total": 0,
                    "aviso": "Não temos produtos nessa categoria no momento.",
                    "categorias_com_produtos": nomes,
                }

        nivel = 0
        if texto:
            consulta = [t for t in _tokens(texto) if t not in STOPWORDS]
            nivel, achados = self._correspondencias_em(consulta, base)
            if not achados and consulta:
                corrigida = self._corrigir(consulta)
                if corrigida != consulta:
                    nivel, achados = self._correspondencias_em(corrigida, base)
                    if achados:
                        resposta["busca_corrigida"] = " ".join(corrigida)
            if ACESSORIOS & set(normalizar(texto).split()) and nivel != 3:
                return {
                    "ambiguo": False,
                    "produtos": [],
                    "total": 0,
                    "possivel_acessorio": True,
                    "aviso": "A loja trabalha apenas com instrumentos musicais; este parece ser um acessório.",
                }
            base = achados

        if preco_min is not None:
            base = [p for p in base if p.preco >= preco_min]
        if preco_max is not None:
            base = [p for p in base if p.preco <= preco_max]

        disponiveis = [p for p in base if self._codigo_disponibilidade(p) == "disponivel"]
        selecionados = disponiveis if so_disponiveis else base

        if texto and nivel == 3 and 2 <= len(selecionados) <= LIMITE_AMBIGUIDADE:
            return {
                **resposta,
                "ambiguo": True,
                "produtos": [],
                "candidatos": [self._visao(p) for p in selecionados],
                "total": len(selecionados),
                "instrucao": "Vários produtos combinam com a busca. Pergunte ao cliente qual deles ele quer antes de afirmar preço ou estoque.",
            }

        resposta.update(
            ambiguo=False,
            produtos=[self._visao(p) for p in selecionados[:LIMITE_RESULTADOS]],
            total=len(selecionados),
        )
        if len(selecionados) > LIMITE_RESULTADOS:
            resposta["aviso"] = (
                f"Mostrando {LIMITE_RESULTADOS} de {len(selecionados)}. Refine a busca (marca, modelo ou faixa de preço) para ver outros."
            )
        if so_disponiveis and not selecionados and base:
            resposta["produtos_indisponiveis"] = [self._visao(p) for p in base[:LIMITE_RESULTADOS]]
            resposta["aviso"] = "Há produtos que combinam, mas nenhum está disponível para compra agora."
        return resposta

    def _correspondencias_em(self, consulta: list[str], base: list[Produto]) -> tuple[int, list[Produto]]:
        if not consulta:
            return 0, list(base)
        nivel, achados = self._correspondencias(consulta)
        permitidos = {p.product_id for p in base}
        achados = [p for p in achados if p.product_id in permitidos]
        return (nivel, achados) if achados else (0, [])

    def detalhar_produto(self, product_id: int | None = None, nome: str | None = None) -> dict:
        if product_id is None and not nome:
            raise ErroFerramenta("ARGUMENTO_INVALIDO", "Informe product_id ou nome do produto.")
        if product_id is not None:
            produto = self._dados.produto(product_id)
            if produto is None:
                raise ErroFerramenta("PRODUTO_NAO_ENCONTRADO", "Não encontrei um produto com esse identificador.")
            return {"produto": self._visao(produto, detalhado=True)}
        busca = self.buscar_produtos(texto=nome, so_disponiveis=False)
        if busca.get("ambiguo"):
            return {"ambiguo": True, "candidatos": busca["candidatos"], "instrucao": busca["instrucao"]}
        if not busca["produtos"]:
            raise ErroFerramenta("PRODUTO_NAO_ENCONTRADO", "Não encontrei esse produto no catálogo.")
        if len(busca["produtos"]) > 1:
            return {
                "ambiguo": True,
                "candidatos": busca["produtos"],
                "instrucao": "Vários produtos combinam. Pergunte ao cliente qual deles ele quer.",
            }
        return {"produto": self._visao(self._dados.produto(busca["produtos"][0]["product_id"]), detalhado=True)}

    def listar_promocoes_ativas(self) -> dict:
        itens = []
        for product_id, promo in sorted(self._promocao_ativa.items()):
            produto = self._dados.produto(product_id)
            if produto is None:
                continue
            visao = self._visao(produto)
            itens.append(
                {
                    "product_id": product_id,
                    "nome": produto.nome,
                    "desconto_percent": promo.desconto_percent,
                    "descricao": promo.descricao,
                    "preco_tabela": visao["preco_tabela"],
                    "preco_promocional": visao["preco_promocional"],
                    "disponibilidade": visao["disponibilidade"],
                }
            )
        return {"promocoes": itens, "total": len(itens)}
