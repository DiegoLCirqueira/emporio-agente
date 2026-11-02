"""Horário de funcionamento da loja (§2) e relógio do agente.

O modelo não tem relógio: o código calcula "aberta ou fechada agora" e entrega o fato
pronto no system prompt (decisão T23). Feriados não são conhecidos.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Campo_Grande")

# weekday(): 0 = segunda ... 6 = domingo. Domingo não aparece: fechado (§2).
HORARIOS: dict[int, tuple[time, time]] = {
    **{d: (time(9, 0), time(18, 0)) for d in range(5)},
    5: (time(9, 0), time(13, 0)),
}

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]


@dataclass(frozen=True)
class SituacaoLoja:
    aberta: bool
    fecha_as: str | None = None
    proxima_abertura: datetime | None = None


def _no_dia(dia: date, hora: time) -> datetime:
    return datetime.combine(dia, hora, tzinfo=FUSO)


def situacao_loja(agora: datetime) -> SituacaoLoja:
    agora = agora.astimezone(FUSO)
    horario = HORARIOS.get(agora.weekday())
    if horario:
        abre, fecha = horario
        if abre <= agora.timetz().replace(tzinfo=None) < fecha:
            return SituacaoLoja(aberta=True, fecha_as=fecha.strftime("%H:%M"))
    for deslocamento in range(8):
        dia = agora.date() + timedelta(days=deslocamento)
        h = HORARIOS.get(dia.weekday())
        if h and _no_dia(dia, h[0]) > agora:
            return SituacaoLoja(aberta=False, proxima_abertura=_no_dia(dia, h[0]))
    raise AssertionError("sem próxima abertura")  # inalcançável: há expediente toda semana


def texto_para_prompt(agora: datetime) -> str:
    agora = agora.astimezone(FUSO)
    s = situacao_loja(agora)
    dia = DIAS_SEMANA[agora.weekday()]
    base = f"Agora são {agora:%H:%M} de {dia}, {agora:%d/%m/%Y} (horário de Campo Grande/MS). "
    if s.aberta:
        fato = f"A loja está ABERTA agora e fecha hoje às {s.fecha_as}."
    else:
        p = s.proxima_abertura
        fato = (f"A loja está FECHADA agora. Próxima abertura: "
                f"{DIAS_SEMANA[p.weekday()]}, {p:%d/%m/%Y} às {p:%H:%M}.")
    return (base + fato + " Este cálculo usa só o horário semanal e não conhece feriados: "
            "se o cliente perguntar sobre um feriado, diga que feriados a loja fica fechada e sugira confirmar.")


def relogio(fixo: datetime | None = None, referencia: date | None = None) -> Callable[[], datetime]:
    """Devolve a função "agora".

    - `fixo`: sempre o mesmo instante (testes).
    - senão: a data de referência ("hoje" do sistema, DD1) com a hora do relógio no
      fuso de Campo Grande, para dia da semana e hora ficarem coerentes entre si.
    """
    if fixo is not None:
        instante = fixo if fixo.tzinfo else fixo.replace(tzinfo=FUSO)
        return lambda: instante

    def agora() -> datetime:
        real = datetime.now(FUSO)
        dia = referencia or real.date()
        return datetime.combine(dia, real.timetz().replace(tzinfo=None), tzinfo=FUSO)

    return agora
