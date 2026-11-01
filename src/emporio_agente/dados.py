"""Carregamento dos CSVs da loja em memória (csv + Decimal, só stdlib).

Os clientes são carregados apenas para autenticar o titular de um pedido: nenhuma
função pública lista ou busca clientes.
"""

import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

PREFIXO_ARQUIVO = "desafio_tecnico_ai_eng - "


@dataclass(frozen=True)
class Categoria:
    category_id: int
    nome: str
    descricao: str


@dataclass(frozen=True)
class Produto:
    product_id: int
    nome: str
    preco: Decimal
    category_id: int
    descricao: str
    estoque: int
    status: str
    specs: dict
    created_at: date


@dataclass(frozen=True)
class Promocao:
    promotion_id: int
    product_id: int
    desconto_percent: int
    descricao: str
    ativa: bool


@dataclass(frozen=True)
class ItemPedido:
    order_id: int
    product_id: int
    quantidade: int


@dataclass(frozen=True)
class Pedido:
    order_id: int
    customer_id: int
    order_date: date
    status: str
    total: Decimal
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None


@dataclass(frozen=True)
class Titular:
    """Titular de um pedido, já autenticado. Só existe depois de uma identificação válida."""

    customer_id: int
    nome: str
    telefone: str
    email: str
    cidade: str


def somente_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def normalizar_email(texto: str) -> str:
    return re.sub(r"\s+", "", texto or "").lower()


def _ler(diretorio: Path, tabela: str) -> list[dict[str, str]]:
    caminho = diretorio / f"{PREFIXO_ARQUIVO}{tabela}.csv"
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in linha.items()} for linha in csv.DictReader(f)]


def _data_ou_none(texto: str) -> date | None:
    return date.fromisoformat(texto) if texto else None


class Dados:
    def __init__(
        self,
        categorias: list[Categoria],
        produtos: list[Produto],
        promocoes: list[Promocao],
        pedidos: list[Pedido],
        itens: list[ItemPedido],
        clientes: list[Titular],
    ):
        self.categorias: tuple[Categoria, ...] = tuple(categorias)
        self.produtos: tuple[Produto, ...] = tuple(sorted(produtos, key=lambda p: p.product_id))
        self.promocoes: tuple[Promocao, ...] = tuple(promocoes)
        self.pedidos: tuple[Pedido, ...] = tuple(sorted(pedidos, key=lambda p: p.order_id))
        self._itens = tuple(itens)
        self._produtos_por_id = {p.product_id: p for p in self.produtos}
        self._categorias_por_id = {c.category_id: c for c in self.categorias}
        self._pedidos_por_id = {p.order_id: p for p in self.pedidos}
        self._clientes_por_id = {c.customer_id: c for c in clientes}

    def produto(self, product_id: int) -> Produto | None:
        return self._produtos_por_id.get(product_id)

    def categoria(self, category_id: int) -> Categoria | None:
        return self._categorias_por_id.get(category_id)

    def pedido(self, order_id: int) -> Pedido | None:
        return self._pedidos_por_id.get(order_id)

    def itens_do_pedido(self, order_id: int) -> tuple[ItemPedido, ...]:
        return tuple(i for i in self._itens if i.order_id == order_id)

    def titular_do_pedido(
        self, order_id: int, telefone: str | None = None, email: str | None = None
    ) -> Titular | None:
        """Devolve o titular só se o telefone (por dígitos) ou o e-mail (minúsculo, sem espaços)
        batem exatamente com o cadastro. Qualquer outra situação devolve None."""
        pedido = self._pedidos_por_id.get(order_id)
        if pedido is None:
            return None
        cliente = self._clientes_por_id.get(pedido.customer_id)
        if cliente is None:
            return None
        tel = somente_digitos(telefone or "")
        mail = normalizar_email(email or "")
        if tel and tel == somente_digitos(cliente.telefone):
            return cliente
        if mail and mail == normalizar_email(cliente.email):
            return cliente
        return None


def carregar_dados(diretorio: Path | str) -> Dados:
    d = Path(diretorio)
    categorias = [
        Categoria(int(r["category_id"]), r["name"], r["description"]) for r in _ler(d, "categories")
    ]
    produtos = [
        Produto(
            product_id=int(r["product_id"]),
            nome=r["name"],
            preco=Decimal(r["price_brl"]),
            category_id=int(r["category_id"]),
            descricao=r["description"],
            estoque=int(r["stock_quantity"]),
            status=r["status"],
            specs=json.loads(r["specs"]) if r["specs"] else {},
            created_at=date.fromisoformat(r["created_at"]),
        )
        for r in _ler(d, "products")
    ]
    promocoes = [
        Promocao(
            int(r["promotion_id"]),
            int(r["product_id"]),
            int(r["discount_percent"]),
            r["description"],
            r["is_active"] == "1",
        )
        for r in _ler(d, "promotions")
    ]
    pedidos = [
        Pedido(
            order_id=int(r["order_id"]),
            customer_id=int(r["customer_id"]),
            order_date=date.fromisoformat(r["order_date"]),
            status=r["status"],
            total=Decimal(r["total_brl"]),
            payment_method=r["payment_method"],
            tracking_code=r["tracking_code"] or None,
            estimated_delivery=_data_ou_none(r["estimated_delivery"]),
            notes=r["notes"] or None,
        )
        for r in _ler(d, "orders")
    ]
    itens = [
        ItemPedido(int(r["order_id"]), int(r["product_id"]), int(r["quantity"]))
        for r in _ler(d, "order_items")
    ]
    clientes = [
        Titular(int(r["customer_id"]), r["name"], r["phone"], r["email"], r["city"])
        for r in _ler(d, "customers")
    ]
    return Dados(categorias, produtos, promocoes, pedidos, itens, clientes)
