"""Horário de funcionamento (§2): fato pronto "aberto ou fechado agora" (decisão T23)."""

from datetime import datetime, timedelta

import pytest

from emporio_agente.horario import FUSO, relogio, situacao_loja, texto_para_prompt


def em(dia, hora, minuto=0):
    """2026-03-30 é segunda-feira."""
    return datetime(2026, 3, 30, hora, minuto, tzinfo=FUSO) + timedelta(days=dia)


@pytest.mark.parametrize(
    "dia,hora,minuto,aberta",
    [
        (1, 10, 0, True),    # terça
        (1, 9, 0, True),     # abre às 09:00
        (1, 8, 59, False),
        (1, 17, 59, True),
        (1, 18, 0, False),   # fecha às 18:00
        (5, 12, 59, True),   # sábado fecha às 13:00
        (5, 13, 0, False),
        (5, 8, 59, False),
        (6, 10, 0, False),   # domingo fechado
    ],
)
def test_aberta_ou_fechada(dia, hora, minuto, aberta):
    assert situacao_loja(em(dia, hora, minuto)).aberta is aberta


def test_aberta_informa_horario_de_fechamento():
    s = situacao_loja(em(1, 10))
    assert s.fecha_as == "18:00"
    assert s.proxima_abertura is None


def test_antes_de_abrir_proxima_abertura_e_hoje():
    assert situacao_loja(em(1, 7)).proxima_abertura == em(1, 9)


def test_depois_de_fechar_na_terca_abre_amanha():
    assert situacao_loja(em(1, 19)).proxima_abertura == em(2, 9)


def test_sexta_depois_de_fechar_abre_sabado():
    assert situacao_loja(em(4, 19)).proxima_abertura == em(5, 9)


def test_sabado_depois_de_fechar_abre_segunda():
    assert situacao_loja(em(5, 14)).proxima_abertura == em(7, 9)


def test_domingo_abre_segunda():
    assert situacao_loja(em(6, 10)).proxima_abertura == em(7, 9)


def test_texto_aberta():
    t = texto_para_prompt(em(1, 10, 30))
    assert "terça-feira, 31/03/2026" in t and "10:30" in t
    assert "ABERTA" in t and "18:00" in t
    assert "Campo Grande" in t


def test_texto_fechada_cita_proxima_abertura():
    t = texto_para_prompt(em(5, 15))
    assert "FECHADA" in t and "sábado" in t
    assert "segunda-feira, 06/04/2026 às 09:00" in t


def test_texto_domingo_fechada():
    assert "FECHADA" in texto_para_prompt(em(6, 10))


def test_texto_avisa_que_feriado_nao_e_conhecido():
    assert "feriado" in texto_para_prompt(em(1, 10)).lower()


def test_relogio_fixo_devolve_o_instante_fixado():
    fixo = em(2, 14, 5)
    assert relogio(fixo=fixo)() == fixo


def test_relogio_sem_fixo_usa_a_data_de_referencia_e_a_hora_do_relogio_no_fuso():
    from datetime import date

    agora = relogio(referencia=date(2026, 3, 31))()
    assert agora.tzinfo is not None
    assert agora.date() == date(2026, 3, 31)
    assert str(agora.tzinfo) == "America/Campo_Grande"
