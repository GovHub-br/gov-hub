"""Interface de linha de comando da publicação (ADR-0019, ADR-0020).

python -m scripts.publicacao validar     # valida o catálogo de publicação (CI)
python -m scripts.publicacao sync        # regera os planos de acesso
python -m scripts.publicacao matriz      # quem enxerga o quê, e com que recorte
python -m scripts.publicacao plano --orgao mgi   # o plano gerado de um órgão
"""

from __future__ import annotations

import argparse
import sys

from ..modelagem.catalogo import ErroCatalogo
from . import acesso as acesso_mod
from .catalogo import CatalogoPublicacao, carregar
from .validacao import planos_dessincronizados, tem_erro, validar


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="publicacao",
        description="Publicação de produtos de dados: dashboards, relatórios e acesso.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    validar_cmd = sub.add_parser(
        "validar", help="valida o catálogo de publicação e os planos de acesso gerados"
    )
    validar_cmd.add_argument(
        "--estrito",
        action="store_true",
        help="tratar avisos como erro (código de órgão não verificado reprova)",
    )

    sub.add_parser("sync", help="regera os planos de acesso a partir do catálogo")
    sub.add_parser("matriz", help="mostra a matriz de acesso")

    plano_cmd = sub.add_parser("plano", help="mostra o plano de acesso de um órgão")
    plano_cmd.add_argument("--orgao", required=True)
    return parser


def _comando_validar(catalogo: CatalogoPublicacao, estrito: bool) -> int:
    problemas = validar(catalogo) + planos_dessincronizados(catalogo)
    for problema in problemas:
        print(problema, file=sys.stderr if problema.nivel == "erro" else sys.stdout)

    erros = sum(1 for p in problemas if p.nivel == "erro")
    avisos = len(problemas) - erros
    print(f"\nCatálogo de publicação validado: {erros} erro(s), {avisos} aviso(s).")
    if tem_erro(problemas) or (estrito and avisos):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _construir_parser().parse_args(argv)
    try:
        catalogo = carregar()
        if args.comando == "validar":
            return _comando_validar(catalogo, estrito=args.estrito)
        if args.comando == "sync":
            for escrita in acesso_mod.sincronizar(catalogo):
                print(escrita)
            return 0
        if args.comando == "matriz":
            print(acesso_mod.render_matriz(catalogo))
            return 0
        print(acesso_mod.renderizar(acesso_mod.montar(catalogo, args.orgao)))
        return 0
    except ErroCatalogo as exc:
        print(f"ERRO  {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
