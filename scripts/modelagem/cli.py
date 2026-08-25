"""Interface de linha de comando das ferramentas de modelagem (ADR-0017).

python -m scripts.modelagem validar      # valida o catálogo (roda no CI)
python -m scripts.modelagem mapa         # o mapa de cruzamento
python -m scripts.modelagem sync         # regera os macros a partir do catálogo
python -m scripts.modelagem gerar ...    # gera modelos dbt
"""

from __future__ import annotations

import argparse
import sys

from . import macros as macros_mod
from . import mapa as mapa_mod
from .catalogo import Catalogo, ErroCatalogo, carregar
from .gerador import gerar_gold, gerar_silver, gerar_sources
from .validacao import tem_erro, validar


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelagem",
        description=(
            "Modelagem de dados a partir do catálogo de sistemas estruturantes."
        ),
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    validar_cmd = sub.add_parser(
        "validar", help="valida o catálogo e a sincronia dos macros gerados"
    )
    validar_cmd.add_argument(
        "--estrito",
        action="store_true",
        help="tratar avisos como erro (mapeamentos não verificados reprovam)",
    )

    mapa_cmd = sub.add_parser("mapa", help="mostra o mapa de cruzamento entre sistemas")
    mapa_cmd.add_argument(
        "--mermaid", action="store_true", help="emitir como grafo Mermaid"
    )

    sub.add_parser("sync", help="regera os macros dbt derivados do catálogo")

    gerar_cmd = sub.add_parser("gerar", help="gera modelos dbt a partir do catálogo")
    gerar_cmd.add_argument(
        "--camada", required=True, choices=("bronze", "silver", "gold")
    )
    gerar_cmd.add_argument("--sistema", help="sistema catalogado (bronze e silver)")
    gerar_cmd.add_argument(
        "--entidade", help="entidade a modelar; nome do modelo em gold"
    )
    gerar_cmd.add_argument("--orgao", help="projeto dbt de destino da gold")
    gerar_cmd.add_argument("--produto", help="produto de dados (pasta e schema da gold)")
    gerar_cmd.add_argument(
        "--cruzar",
        action="append",
        default=[],
        metavar="SISTEMA.ENTIDADE",
        help="entidade a cruzar na gold; repita para cada uma (a primeira é a base)",
    )
    gerar_cmd.add_argument(
        "--forcar", action="store_true", help="sobrescrever arquivos existentes"
    )
    return parser


def _comando_validar(catalogo: Catalogo, estrito: bool) -> int:
    problemas = validar(catalogo)
    for problema in problemas:
        print(problema, file=sys.stderr if problema.nivel == "erro" else sys.stdout)

    if not macros_mod.esta_sincronizado(catalogo):
        print(
            "ERRO   macros dbt: chaves_geradas.sql está fora de sincronia com "
            "catalogo/chaves.yml. Rode: make catalogo-sync",
            file=sys.stderr,
        )
        return 1

    erros = sum(1 for p in problemas if p.nivel == "erro")
    avisos = len(problemas) - erros
    print(f"\nCatálogo validado: {erros} erro(s), {avisos} aviso(s).")
    if tem_erro(problemas) or (estrito and avisos):
        return 1
    return 0


def _comando_gerar(catalogo: Catalogo, args: argparse.Namespace) -> int:
    if args.camada == "gold":
        faltando = [
            nome
            for nome, valor in (
                ("--orgao", args.orgao),
                ("--produto", args.produto),
                ("--entidade", args.entidade),
            )
            if not valor
        ]
        if faltando:
            raise ErroCatalogo(
                f"camada gold exige {', '.join(faltando)} (além de --cruzar)."
            )
        escritas = gerar_gold(
            catalogo,
            orgao=args.orgao,
            produto=args.produto,
            nome=args.entidade,
            referencias=args.cruzar,
            forcar=args.forcar,
        )
    elif args.camada == "bronze":
        if not args.sistema:
            raise ErroCatalogo("camada bronze exige --sistema.")
        escritas = gerar_sources(catalogo, args.sistema, forcar=args.forcar)
    else:
        if not (args.sistema and args.entidade):
            raise ErroCatalogo("camada silver exige --sistema e --entidade.")
        escritas = gerar_silver(catalogo, args.sistema, args.entidade, forcar=args.forcar)

    for escrita in escritas:
        print(escrita)
    if any(e.acao == "preservado" for e in escritas):
        print("\nArquivo existente preservado. Use --forcar para sobrescrever.")
    if any(e.acao != "preservado" for e in escritas):
        # O gerador prioriza SQL legível; a formatação canônica é do sqlfmt.
        print("\nRode `make format` para aplicar o sqlfmt ao SQL gerado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _construir_parser().parse_args(argv)
    try:
        catalogo = carregar()
        if args.comando == "validar":
            return _comando_validar(catalogo, estrito=args.estrito)
        if args.comando == "mapa":
            print(
                mapa_mod.render_mermaid(catalogo)
                if args.mermaid
                else mapa_mod.render(catalogo)
            )
            return 0
        if args.comando == "sync":
            for escrita in macros_mod.sincronizar(catalogo):
                print(escrita)
            return 0
        return _comando_gerar(catalogo, args)
    except ErroCatalogo as exc:
        print(f"ERRO  {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
