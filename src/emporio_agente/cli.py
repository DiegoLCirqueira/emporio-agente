"""Interface de linha de comando: REPL e modo de mensagem única."""

import argparse
import json
import logging
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from emporio_agente.agente import Agente, FerramentaChamada, RespostaAgente, criar_agente
from emporio_agente.config import RAIZ_REPO, Config, ConfigError
from emporio_agente.provedores.base import ProvedorErro

log = logging.getLogger(__name__)

SAUDACAO = "Empório da Música: atendimento. Escreva sua mensagem (digite 'sair' para encerrar)."
DESPEDIDA = "Até logo!"
COMANDOS_SAIDA = {"sair", "exit", "quit"}
AJUDA_ENV = (
    "Não encontrei a chave da API da Anthropic (ANTHROPIC_API_KEY).\n"
    "Para configurar: copie .env.example para .env na raiz do projeto e preencha "
    "ANTHROPIC_API_KEY=sua-chave (ou defina a variável de ambiente ANTHROPIC_API_KEY)."
)


class _SemTraceback(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.exc_info = None
        record.exc_text = None
        return super().format(record)


def _configurar_logging(debug: bool) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(levelname)s %(name)s: %(message)s") if debug else _SemTraceback("[aviso] %(message)s")
    )
    raiz = logging.getLogger()
    raiz.handlers[:] = [handler]
    raiz.setLevel(logging.DEBUG if debug else logging.WARNING)


def _utf8() -> None:
    for fluxo in (sys.stdout, sys.stderr, sys.stdin):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar:
            try:
                reconfigurar(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def linha_ferramenta(f: FerramentaChamada) -> str:
    argumentos = json.dumps(f.argumentos, ensure_ascii=False, default=str)
    situacao = "ok" if f.ok else f"erro {f.codigo_erro}"
    return f"{f.nome} {argumentos} -> {situacao}"


class Transcript:
    """Grava a conversa em transcripts/AAAA-MM-DD-HHMMSS.md; o arquivo só nasce na 1ª fala."""

    def __init__(self, pasta: Path, ativo: bool):
        self._pasta = pasta
        self._ativo = ativo
        self._arquivo: Path | None = None

    def registrar(self, cliente: str, resposta: RespostaAgente) -> None:
        if not self._ativo:
            return
        if self._arquivo is None:
            self._pasta.mkdir(parents=True, exist_ok=True)
            agora = datetime.now()
            self._arquivo = self._pasta / f"{agora:%Y-%m-%d-%H%M%S}.md"
            self._arquivo.write_text(f"# Conversa de {agora:%d/%m/%Y %H:%M:%S}\n", encoding="utf-8")
        blocos = [f"\n**Cliente:** {cliente}\n"]
        if resposta.ferramentas_chamadas:
            blocos.append("**Ferramentas:**\n" + "\n".join(f"- `{linha_ferramenta(f)}`" for f in resposta.ferramentas_chamadas) + "\n")
        blocos.append(f"**Atendente:** {resposta.texto}\n")
        with self._arquivo.open("a", encoding="utf-8") as f:
            f.write("\n".join(blocos))


def _turno(agente, mensagem: str, mostrar: bool, transcript: Transcript, prefixo: str = "") -> RespostaAgente:
    resposta = agente.responder(mensagem)
    if mostrar:
        if resposta.ferramentas_chamadas:
            for f in resposta.ferramentas_chamadas:
                print(f"  [ferramenta] {linha_ferramenta(f)}")
        else:
            print("  [ferramenta] nenhuma ferramenta chamada")
    print(f"{prefixo}{resposta.texto}")
    transcript.registrar(mensagem, resposta)
    return resposta


def _repl(agente, mostrar: bool, transcript: Transcript) -> int:
    print(SAUDACAO)
    while True:
        try:
            entrada = input("Você: ").strip()
            if not entrada:
                continue
            if entrada.lower() in COMANDOS_SAIDA:
                break
            print()
            _turno(agente, entrada, mostrar, transcript, prefixo="Atendente: ")
            print()
        except (EOFError, KeyboardInterrupt):
            print()
            break
    print(DESPEDIDA)
    return 0


def main(
    argv: list[str] | None = None,
    *,
    config: Config | None = None,
    fabrica: Callable[[Config], Agente] | None = None,
    transcripts_dir: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="emporio-agente", description="Atendimento da Empório da Música.")
    parser.add_argument("-m", "--mensagem", help="envia uma única mensagem e imprime a resposta")
    parser.add_argument("--mostrar-ferramentas", action="store_true", help="mostra as ferramentas chamadas em cada turno")
    parser.add_argument("--debug", action="store_true", help="mostra logs detalhados e tracebacks")
    args = parser.parse_args(argv)

    _utf8()
    _configurar_logging(args.debug)

    try:
        config = config or Config.from_env()
    except ConfigError as e:
        print(f"Erro de configuração: {e}", file=sys.stderr)
        return 2
    try:
        agente = (fabrica or criar_agente)(config)
    except ProvedorErro as e:
        log.debug("ProvedorErro ao criar o agente: %s", e)
        print(AJUDA_ENV, file=sys.stderr)
        return 2
    except OSError as e:
        print(f"Não consegui ler os dados da loja em {config.dados_dir}: {e}", file=sys.stderr)
        return 2

    transcript = Transcript(transcripts_dir or RAIZ_REPO / "transcripts", config.salvar_transcripts)
    if args.mensagem is not None:
        resposta = _turno(agente, args.mensagem, args.mostrar_ferramentas, transcript)
        return 1 if resposta.falhou else 0
    return _repl(agente, args.mostrar_ferramentas, transcript)
