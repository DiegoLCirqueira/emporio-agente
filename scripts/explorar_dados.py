"""Perfil dos CSVs de data/ (somente stdlib). Uso: python scripts/explorar_dados.py"""
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(__file__).resolve().parent.parent / "data"
PFX = "desafio_tecnico_ai_eng - "
TABLES = ["categories", "customers", "products", "orders", "order_items", "promotions"]
HOJE = date.today()


def load(name):
    raw = (DATA / f"{PFX}{name}.csv").read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        txt = raw.decode("utf-8-sig")
        enc = "utf-8" + (" (BOM)" if bom else "")
    except UnicodeDecodeError:
        txt, enc = raw.decode("latin-1"), "latin-1"
    delim = csv.Sniffer().sniff(txt[:2000], delimiters=",;\t|").delimiter
    rows = list(csv.DictReader(txt.splitlines(), delimiter=delim))
    return rows, enc, delim, ("\r\n" in txt), txt.endswith("\n")


def infer(v):
    v = v.strip()
    if v == "":
        return "vazio"
    if re.fullmatch(r"-?\d+", v):
        return "int"
    if re.fullmatch(r"-?\d+\.\d+", v):
        return "float(ponto)"
    if re.fullmatch(r"-?\d+,\d+", v):
        return "float(virgula)"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return "data ISO"
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", v):
        return "data BR"
    if "R$" in v:
        return "moeda texto"
    if v[:1] in "{[":
        try:
            json.loads(v)
            return "json"
        except ValueError:
            return "json invalido"
    return "texto"


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def num(v):
    try:
        return float(v.replace("R$", "").replace(",", ".").strip())
    except ValueError:
        return None


def dt(v):
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def hdr(t):
    print(f"\n{'=' * 70}\n{t}\n{'=' * 70}")


data = {}
for t in TABLES:
    rows, enc, delim, crlf, nl = load(t)
    data[t] = rows
    hdr(f"TABELA {t}  ({len(rows)} linhas)")
    print(f"encoding={enc} sep={delim!r} CRLF={crlf} newline_final={nl}")
    for c in rows[0].keys():
        vals = [r[c] if r[c] is not None else "" for r in rows]
        tipos = Counter(infer(v) for v in vals)
        nulos = sum(1 for v in vals if v.strip() == "")
        espacos = [v for v in vals if v != v.strip() or "  " in v]
        print(f"- {c}: tipos={dict(tipos)} nulos={nulos} unicos={len(set(vals))}"
              + (f" ESPACOS_EXTRAS={espacos[:3]}" if espacos else ""))
    full = Counter(tuple(r.values()) for r in rows)
    dup = [k for k, n in full.items() if n > 1]
    print(f"linhas inteiras duplicadas: {len(dup)}", dup[:3])

hdr("CHAVES PRIMARIAS")
pk = {"categories": "category_id", "customers": "customer_id", "products": "product_id",
      "orders": "order_id", "promotions": "promotion_id"}
for t, k in pk.items():
    c = Counter(r[k] for r in data[t])
    d = {x: n for x, n in c.items() if n > 1}
    print(f"{t}.{k}: unico={not d} duplicados={d}")
c = Counter((r["order_id"], r["product_id"]) for r in data["order_items"])
print("order_items (order_id,product_id) duplicado:", {k: n for k, n in c.items() if n > 1})

hdr("INTEGRIDADE REFERENCIAL (orfaos)")
ids = {t: {r[k] for r in data[t]} for t, k in pk.items()}
fks = [("products", "category_id", "categories"), ("orders", "customer_id", "customers"),
       ("order_items", "order_id", "orders"), ("order_items", "product_id", "products"),
       ("promotions", "product_id", "products")]
for t, col, ref in fks:
    orf = sorted({r[col] for r in data[t] if r[col].strip() and r[col] not in ids[ref]},
                 key=lambda x: int(x) if x.isdigit() else 0)
    print(f"{t}.{col} -> {ref}: orfaos={orf}")
print("categorias sem produtos:", sorted(ids["categories"] - {r["category_id"] for r in data["products"]}))
print("clientes sem pedidos:", len(ids["customers"] - {r["customer_id"] for r in data["orders"]}), "de", len(ids["customers"]))
print("pedidos sem itens:", sorted(ids["orders"] - {r["order_id"] for r in data["order_items"]}, key=int))
print("produtos nunca pedidos:", len(ids["products"] - {r["product_id"] for r in data["order_items"]}), "de", len(ids["products"]))

hdr("PRODUCTS: dominio")
P = data["products"]
print("status:", Counter(r["status"] for r in P))
print("category_id:", sorted(Counter(r["category_id"] for r in P).items(), key=lambda x: int(x[0])))
print("precos <=0:", [(r["product_id"], r["price_brl"]) for r in P if (num(r["price_brl"]) or 0) <= 0])
print("precos nao numericos:", [(r["product_id"], r["price_brl"]) for r in P if num(r["price_brl"]) is None])
pr = sorted((num(r["price_brl"]), r["product_id"], r["name"]) for r in P if num(r["price_brl"]) is not None)
print("preco min/max:", pr[0], pr[-1])
print("estoque <0:", [(r["product_id"], r["stock_quantity"]) for r in P if (num(r["stock_quantity"]) or 0) < 0])
print("estoque 0:", [(r["product_id"], r["status"]) for r in P if num(r["stock_quantity"]) == 0])
print("estoque nao inteiro:", [(r["product_id"], r["stock_quantity"]) for r in P if not re.fullmatch(r"-?\d+", r["stock_quantity"])])
print("status x estoque inconsistente:",
      [(r["product_id"], r["status"], r["stock_quantity"]) for r in P
       if (r["status"] == "active" and num(r["stock_quantity"]) == 0)
       or (r["status"] != "active" and (num(r["stock_quantity"]) or 0) > 0)])
bad_specs = []
for r in P:
    try:
        json.loads(r["specs"])
    except ValueError:
        bad_specs.append(r["product_id"])
print("specs JSON invalido/vazio:", bad_specs)
print("created_at formatos:", Counter(infer(r["created_at"]) for r in P),
      "futuras:", [r["product_id"] for r in P if (dt(r["created_at"]) or date.min) > HOJE])
print("descricao vazia:", [r["product_id"] for r in P if not r["description"].strip()])
nm = defaultdict(list)
for r in P:
    nm[norm(r["name"])].append(r["product_id"])
print("nomes duplicados (normalizados):", {k: v for k, v in nm.items() if len(v) > 1})
marcas = Counter(r["name"].split()[0] for r in P)
print("primeira palavra do nome:", dict(marcas))
mn = defaultdict(set)
for m in marcas:
    mn[norm(m)].add(m)
print("variacoes de marca por caixa/acento:", {k: v for k, v in mn.items() if len(v) > 1})
ids_p = [int(r["product_id"]) for r in P]
print("ids fora de ordem no arquivo:", [b for a, b in zip(ids_p, ids_p[1:]) if b < a])
print("ids ausentes na sequencia", min(ids_p), "-", max(ids_p), ":", sorted(set(range(min(ids_p), max(ids_p) + 1)) - set(ids_p)))
bycat = Counter(r["category_id"] for r in P)
print("produtos por categoria:", dict(sorted(bycat.items(), key=lambda x: int(x[0]))))
spec_keys = defaultdict(set)
for r in P:
    try:
        spec_keys[r["category_id"]] |= set(json.loads(r["specs"]))
    except ValueError:
        pass
print("chaves de specs por categoria:", {k: sorted(v) for k, v in sorted(spec_keys.items())})
ds = Counter()
for r in P:
    try:
        ds[tuple(sorted(json.loads(r["specs"])))] += 1
    except ValueError:
        pass
print("specs vazios {}:", [r["product_id"] for r in P if r["specs"].strip() in ("{}", "")])

hdr("CATEGORIES")
for r in data["categories"]:
    print(r["category_id"], "|", r["name"], "|", r["description"][:70])

hdr("CUSTOMERS: qualidade")
C = data["customers"]
print("cidades:", dict(Counter(r["city"] for r in C)))
print("telefone fora do padrao:", [(r["customer_id"], r["phone"]) for r in C if not re.fullmatch(r"\(\d{2}\) 9\d{4}-\d{4}", r["phone"])])
print("telefones repetidos:", [k for k, n in Counter(r["phone"] for r in C).items() if n > 1])
print("emails repetidos:", [k for k, n in Counter(r["email"].lower() for r in C).items() if n > 1])
print("email invalido:", [(r["customer_id"], r["email"]) for r in C if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", r["email"])])
print("dominios:", dict(Counter(r["email"].split("@")[-1] for r in C)))
nc = defaultdict(list)
for r in C:
    nc[norm(r["name"])].append(r["customer_id"])
print("nomes duplicados:", {k: v for k, v in nc.items() if len(v) > 1})
print("nomes sem acento (normalizado == original, mas pt-BR esperaria acento):",
      [(r["customer_id"], r["name"]) for r in C if r["name"] in ("Joao Silva", "Leticia Gomes", "Julia Carvalho")])
print("nomes com 2 palavras:", sum(1 for r in C if len(r["name"].split()) == 2), "de", len(C))
print("primeiro nome repetido (ambiguidade de busca):", {k: v for k, v in Counter(r["name"].split()[0] for r in C).items() if v > 1})
print("email nao deriva do nome:", [(r["customer_id"], r["name"], r["email"]) for r in C if norm(r["name"].split()[0]) not in norm(r["email"])])

hdr("ORDERS: dominio")
O = data["orders"]
print("status:", dict(Counter(r["status"] for r in O)))
print("payment_method:", dict(Counter(r["payment_method"] for r in O)))
print("order_date:", dict(Counter(infer(r["order_date"]) for r in O)), "| estimated_delivery:", dict(Counter(infer(r["estimated_delivery"]) for r in O)))
print("total_brl formatos:", dict(Counter(infer(r["total_brl"]) for r in O)), "| <=0:", [r["order_id"] for r in O if (num(r["total_brl"]) or 0) <= 0])
print("order_date intervalo:", min(r["order_date"] for r in O), "->", max(r["order_date"] for r in O), "| hoje:", HOJE)
print("order_date no futuro:", [(r["order_id"], r["order_date"], r["status"]) for r in O if (dt(r["order_date"]) or date.min) > HOJE])
print("entrega estimada < pedido:", [r["order_id"] for r in O if dt(r["estimated_delivery"]) and dt(r["order_date"]) and dt(r["estimated_delivery"]) < dt(r["order_date"])])
print("prazo estimado (dias) min/max:", (lambda l: (min(l), max(l)))([(dt(r["estimated_delivery"]) - dt(r["order_date"])).days for r in O if r["estimated_delivery"]]))
print("tracking por status (qtd com codigo / total):", {s: (sum(1 for r in O if r["status"] == s and r["tracking_code"]), n) for s, n in Counter(r["status"] for r in O).items()})
print("tracking fora do padrao:", [(r["order_id"], r["tracking_code"]) for r in O if r["tracking_code"] and not re.fullmatch(r"BR[A-Z0-9]{9}BR", r["tracking_code"])])
print("tracking duplicado:", [k for k, n in Counter(r["tracking_code"] for r in O if r["tracking_code"]).items() if n > 1])
print("notes preenchidas por status:", dict(Counter(r["status"] for r in O if r["notes"].strip())))
print("pending/confirmed com >30 dias vs hoje:", [(r["order_id"], r["order_date"], r["status"]) for r in O if r["status"] in ("pending", "confirmed") and (HOJE - dt(r["order_date"])).days > 30])
print("shipped com estimated_delivery ja vencida:", [(r["order_id"], r["estimated_delivery"]) for r in O if r["status"] == "shipped" and dt(r["estimated_delivery"]) < HOJE])

hdr("ORDERS x ORDER_ITEMS: total confere?")
prod = {r["product_id"]: num(r["price_brl"]) for r in P}
soma = defaultdict(float)
orfaos = defaultdict(list)
for it in data["order_items"]:
    pr_ = prod.get(it["product_id"])
    if pr_ is None:
        orfaos[it["order_id"]].append(it["product_id"])
        continue
    soma[it["order_id"]] += pr_ * int(it["quantity"])
for r in O:
    s = soma.get(r["order_id"])
    t = num(r["total_brl"])
    if s is None or abs(s - t) > 0.01:
        print(f"  pedido {r['order_id']}: total={t} soma_itens(preco atual)={s} status={r['status']} produtos_orfaos={orfaos.get(r['order_id'])}")
print("quantity invalida:", [it for it in data["order_items"] if not re.fullmatch(r"[1-9]\d*", it["quantity"])])
st = {p["product_id"]: p["status"] for p in P}
print("itens com produto nao-active:", [(it["order_id"], it["product_id"], st[it["product_id"]]) for it in data["order_items"] if st.get(it["product_id"]) not in (None, "active")])
print("order_ids em order_items:", sorted({it["order_id"] for it in data["order_items"]}, key=int))

hdr("PROMOTIONS")
PR = data["promotions"]
print("colunas:", list(PR[0].keys()), "-> sem data inicio/fim: vigencia nao verificavel")
print("is_active:", dict(Counter(r["is_active"] for r in PR)))
print("discount_percent min/max:", min(int(r["discount_percent"]) for r in PR), max(int(r["discount_percent"]) for r in PR))
print("descricoes:", dict(Counter(r["description"] for r in PR)))
ativas = [r for r in PR if r["is_active"] == "1"]
print("ativas:", [(r["promotion_id"], r["product_id"], r["discount_percent"], r["description"]) for r in ativas])
bp = defaultdict(list)
for r in PR:
    bp[r["product_id"]].append((r["promotion_id"], r["discount_percent"], r["is_active"]))
print("produtos com >1 promocao (historico sobreposto):", {k: v for k, v in bp.items() if len(v) > 1})
bpa = defaultdict(list)
for r in ativas:
    bpa[r["product_id"]].append(r["promotion_id"])
print("produtos com >1 promocao ATIVA:", {k: v for k, v in bpa.items() if len(v) > 1})
pp = {p["product_id"]: p for p in P}
print("promocao ativa em produto nao-active/sem estoque:", [(r["promotion_id"], r["product_id"], pp[r["product_id"]]["status"], pp[r["product_id"]]["stock_quantity"]) for r in ativas if r["product_id"] in pp and (pp[r["product_id"]]["status"] != "active" or pp[r["product_id"]]["stock_quantity"] == "0")])
print("preco com desconto das ativas:", [(r["product_id"], pp[r["product_id"]]["name"], pp[r["product_id"]]["price_brl"], round(num(pp[r["product_id"]]["price_brl"]) * (1 - int(r["discount_percent"]) / 100), 2)) for r in ativas if r["product_id"] in pp])
print("promos ativas de nome sazonal:", [(r["promotion_id"], r["description"]) for r in ativas if r["description"] in ("Black Friday", "Promoção de Páscoa", "Liquidação de Inverno")])
print("\nFim.")
