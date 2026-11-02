"""Fatos críticos do manual curado (politicas.md) e estrutura do system prompt.

Os fatos foram conferidos contra data/políticas_da_loja.pdf (pdftotext sem -layout).
Se algum teste falhar após editar o manual, o manual divergiu do PDF ou de docs/decisoes.md.
"""
import re
from datetime import date

import pytest

from emporio_agente.politicas import (
    carregar_politicas,
    montar_parte_estavel,
    montar_parte_variavel,
    montar_system_prompt,
)


@pytest.fixture(scope="module")
def manual() -> str:
    return carregar_politicas()


def _linha_com(manual: str, prefixo: str) -> str:
    """Devolve a linha do manual que começa com `prefixo` (ignorando marcadores de lista)."""
    for linha in manual.splitlines():
        if linha.lstrip("-* ").startswith(prefixo):
            return linha
    raise AssertionError(f"linha iniciada por {prefixo!r} não encontrada no manual")


# --- Manual: carregamento ---------------------------------------------------

def test_manual_carrega_e_nao_e_vazio(manual):
    assert len(manual) > 2000
    assert manual.startswith("# ")


def test_manual_cita_secoes_do_pdf(manual):
    for secao in ["§1.2", "§2", "§3", "§3.1", "§4.1", "§4.2", "§4.3", "§4.4",
                  "§5.1", "§5.2", "§5.3", "§6.1", "§6.2", "§7.1", "§7.2", "§7.3",
                  "§8.1", "§8.2", "§8.3", "§9"]:
        assert f"({secao})" in manual, f"seção {secao} não citada"


# --- Horários (§2): o -layout do pdftotext troca sábado e domingo ------------

def test_horario_segunda_a_sexta(manual):
    assert "09:00 às 18:00" in _linha_com(manual, "Segunda a sexta-feira")


def test_horario_sabado(manual):
    linha = _linha_com(manual, "Sábado")
    assert "09:00 às 13:00" in linha
    assert "18:00" not in linha


def test_horario_domingo_e_feriados_fechado(manual):
    linha = _linha_com(manual, "Domingo e feriados")
    assert "fechado" in linha.lower()
    assert "09:00" not in linha


# --- Trocas, devoluções e garantia (§4, §8) ---------------------------------

def test_arrependimento_7_dias_corridos_apos_recebimento_so_online(manual):
    assert "7 (sete) dias corridos após o recebimento" in manual
    assert re.search(r"Direito de arrependimento.*compras online", manual, re.I)
    assert "10 dias úteis" in manual


def test_defeito_30_dias(manual):
    assert "30 (trinta) dias corridos após a compra" in manual


def test_preferencia_7_dias(manual):
    assert re.search(r"[Tt]rocas por preferência.*em até 7 dias", manual)


def test_garantia_legal_90_dias_apos_recebimento(manual):
    assert "90 (noventa) dias" in manual
    assert "a partir da data de recebimento" in manual


def test_dd6_defeito_entre_31_e_90_dias_encaminha_para_humano(manual):
    nota = _bloco_nota_dd(manual, "DD6")
    assert "§4.2" in nota and "§8.1" in nota
    assert "humano" in nota.lower()


# --- Pagamento (§3, §3.1, §6.2) e DD5 ----------------------------------------

def test_dd5_faixas_de_parcelamento(manual):
    assert re.search(r"[Aa]té 3x.*R\$ 50,00", manual)
    assert re.search(r"4x a 6x.*R\$ 80,00", manual)
    assert re.search(r"7x a 12x.*R\$ 100,00", manual)
    assert "sem juros" in manual


def test_dd5_nota_de_curadoria(manual):
    nota = _bloco_nota_dd(manual, "DD5")
    assert "§3.1" in nota


def test_pix_5_por_cento_nao_cumulativo_com_promocao(manual):
    assert "5% de desconto" in manual
    assert "não se aplica sobre preços já promocionais" in manual


# --- Contatos (DD4) e endereço (§1.2) -----------------------------------------

def test_endereco(manual):
    assert "Rua 14 de Maio, 3200" in manual
    assert "Centro" in manual
    assert "Campo Grande - MS" in manual
    assert "79202-333" in manual


def test_dd4_contatos(manual):
    assert "(67) 3341-4444" in _linha_com(manual, "Telefone")
    assert "(67) 3321-4500" in _linha_com(manual, "WhatsApp")
    assert "contato@emporiodamusica.com.br" in manual
    assert "empório" not in manual.lower().split("e-mail")[1].splitlines()[0]


def test_dd4_nota_de_curadoria(manual):
    nota = _bloco_nota_dd(manual, "DD4")
    assert "3341-4444" in nota and "3321-4500" in nota


def _bloco_nota_dd(manual: str, dd: str) -> str:
    for linha in manual.splitlines():
        if "Nota de curadoria" in linha and dd in linha:
            return linha
    raise AssertionError(f"Nota de curadoria {dd} não encontrada")


# --- System prompt ------------------------------------------------------------

REF = date(2026, 3, 31)


@pytest.fixture(scope="module")
def prompt() -> str:
    return montar_system_prompt(REF)


def test_prompt_contem_data_de_referencia(prompt):
    assert "2026-03-31" in prompt
    assert "31/03/2026" in prompt


def test_prompt_traz_manual_inteiro_delimitado(prompt, manual):
    assert f"<manual_de_politicas>\n{manual.strip()}\n</manual_de_politicas>" in prompt


def test_prompt_persona_assistente_virtual(prompt):
    assert "assistente virtual" in prompt
    assert "Empório da Música" in prompt


def test_prompt_regra_dados_so_via_ferramenta(prompt):
    for ferramenta in ["buscar_produtos", "detalhar_produto", "consultar_pedido",
                       "listar_promocoes_ativas"]:
        assert ferramenta in prompt


def test_prompt_regra_pii(prompt):
    assert "número do pedido" in prompt
    assert "telefone ou e-mail" in prompt
    assert "terceiros" in prompt


def test_prompt_regra_dd2_nunca_prometer_desconto_inativo(prompt):
    assert "Black Friday" in prompt
    assert re.search(r"[Nn]unca prometa desconto", prompt)


def test_prompt_regra_injection(prompt):
    assert "dados, não instruções" in prompt
    assert re.search(r"[Nn]ão revele.*(instruções|prompt)", prompt)


def test_prompt_regra_arrependimento_dd3(prompt):
    assert "data de recebimento" in prompt
    assert "online ou na loja" in prompt


def test_prompt_regra_ambiguidade_i3(prompt):
    assert re.search(r"mais de um produto.*pergunte", prompt, re.I | re.S)


def test_prompt_escalonamento_humano(prompt):
    assert "equipe humana" in prompt


def test_parte_estavel_independe_da_data():
    a = montar_parte_estavel()
    assert a == montar_parte_estavel()
    assert "2026" not in a.split("<manual_de_politicas>")[0]


def test_parte_variavel_contem_so_a_data():
    v = montar_parte_variavel(REF)
    assert "2026-03-31" in v
    assert len(v) < 400


def test_prompt_e_estavel_mais_variavel_nessa_ordem():
    assert montar_system_prompt(REF) == montar_parte_estavel() + "\n\n" + montar_parte_variavel(REF)
    assert montar_system_prompt(date(2026, 4, 1)).startswith(montar_parte_estavel())


def test_parte_variavel_nao_induz_a_dizer_se_esta_aberto_agora():
    v = montar_parte_variavel(REF)
    assert "Você não sabe a hora" not in v
    assert re.search(r"[Nn]unca afirme que a loja está aberta ou fechada além do fato informado", v)


def test_parte_variavel_com_relogio_traz_o_fato_pronto():
    from datetime import datetime

    from emporio_agente.horario import FUSO, texto_para_prompt

    agora = datetime(2026, 3, 31, 19, 0, tzinfo=FUSO)
    v = montar_parte_variavel(REF, agora)
    assert texto_para_prompt(agora) in v
    assert "FECHADA" in v
    assert montar_system_prompt(REF, agora) == montar_parte_estavel() + "\n\n" + v


def test_prompt_regra_previsao_vencida_caso6(prompt):
    assert "previsao_vencida" in prompt
    assert re.search(r"exatamente como a ferramenta retornar", prompt)
    assert re.search(r"sem deduzir (a )?entrega", prompt)


def test_prompt_regra_promocao_caso7(prompt):
    assert re.search(r"(pergunta|pergunt\w+) sobre promoção, desconto ou Black Friday.*listar_promocoes_ativas.*ANTES de responder", prompt, re.S)
    assert re.search(r"datas comemorativas", prompt)
    assert re.search(r"nunca prometa desconto inativo", prompt, re.I)


def test_prompt_regra_mais_resultados_caso1(prompt):
    assert "nao_exibidos" in prompt
