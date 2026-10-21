"""Comprueba el enrutamiento del agente `router` con mensajes de ejemplo.

Uso:
    python scripts/probar_router.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.router.graph import grafo  # noqa: E402

MENSAJES = [
    "¿tienen la polera azul en talla M?",
    "mi pedido 4521 llegó roto",
    "hola",
    "¿cuánto cuesta el envío a Valparaíso?",
    "quiero devolver unas zapatillas",
    "¿qué hora es en Tokio?",
]


def main() -> int:
    for numero, mensaje in enumerate(MENSAJES, start=1):
        estado = grafo.invoke(
            {"mensaje": mensaje},
            config={"configurable": {"thread_id": f"prueba-router-{numero}"}},
        )
        print(f"{numero}. {mensaje}")
        print(f"   ruta: {estado.get('ruta')}")
        print(f"   motivo: {estado.get('motivo')}")
        print(f"   respuesta: {estado.get('respuesta')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
