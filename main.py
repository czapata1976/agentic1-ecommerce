"""Ejecuta un agente desde la raíz del proyecto.

Uso:
    python main.py {nombre_agente} "mensaje" [--saltos] [--diagrama]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.agentes import AgenteDesconocido, cargar_agente, nombres_disponibles  # noqa: E402


def construir_parser() -> argparse.ArgumentParser:
    disponibles = ", ".join(nombres_disponibles()) or "(ninguno)"
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Ejecuta un agente de src/{nombre_agente} sobre un mensaje.",
    )
    parser.add_argument("agente", help=f"Nombre del agente. Disponibles: {disponibles}")
    parser.add_argument("mensaje", nargs="?", default="", help="Mensaje para el agente")
    parser.add_argument(
        "--saltos",
        action="store_true",
        help="Imprime los nodos por los que pasó el grafo",
    )
    parser.add_argument(
        "--diagrama",
        action="store_true",
        help="Imprime el Mermaid del grafo sin ejecutarlo",
    )
    parser.add_argument(
        "--thread",
        default="cli",
        help="Identificador de memoria del grafo (thread_id). Por defecto: cli",
    )
    return parser


def _ejecutar_con_saltos(
    grafo: Any, mensaje: str, config: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    saltos: list[str] = []
    estado: dict[str, Any] = {}
    for paso in grafo.stream({"mensaje": mensaje}, config=config, stream_mode="updates"):
        for nodo, salida in paso.items():
            saltos.append(nodo)
            if isinstance(salida, dict):
                estado.update(salida)
    return saltos, estado


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    try:
        modulo = cargar_agente(args.agente)
    except AgenteDesconocido as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    grafo = modulo.grafo

    if args.diagrama:
        print(grafo.get_graph().draw_mermaid())
        return 0

    if not args.mensaje.strip():
        print(
            f'[error] Falta el mensaje. Ejemplo: python main.py {args.agente} "hola"',
            file=sys.stderr,
        )
        return 2

    config = {"configurable": {"thread_id": args.thread}}

    try:
        if args.saltos:
            saltos, estado = _ejecutar_con_saltos(grafo, args.mensaje, config)
            print(f"[saltos] {' -> '.join(saltos)}")
            motivo = str(estado.get("motivo", "")).strip()
            if motivo:
                print(f"[motivo] {motivo}")
        else:
            estado = grafo.invoke({"mensaje": args.mensaje}, config=config)
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    respuesta = str(estado.get("respuesta", "")).strip()
    print(respuesta or "[sin respuesta]")
    return 0 if respuesta else 1


if __name__ == "__main__":
    raise SystemExit(main())
