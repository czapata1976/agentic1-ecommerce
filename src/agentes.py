"""Carga dinámica de agentes alojados en src/{nombre_agente}/graph.py."""

from __future__ import annotations

import importlib
import re
from pathlib import Path
from types import ModuleType

RAIZ_SRC = Path(__file__).resolve().parent
_PATRON_NOMBRE = re.compile(r"^[a-z][a-z0-9_]*$")


class AgenteDesconocido(ValueError):
    """El agente solicitado no existe o su nombre no es válido."""


def nombres_disponibles() -> list[str]:
    """Agentes con un graph.py dentro de src/."""
    return sorted(
        carpeta.name
        for carpeta in RAIZ_SRC.iterdir()
        if carpeta.is_dir()
        and not carpeta.name.startswith(("_", "."))
        and (carpeta / "graph.py").is_file()
    )


def cargar_agente(nombre: str) -> ModuleType:
    """Importa y devuelve el módulo graph.py del agente indicado."""
    if not _PATRON_NOMBRE.match(nombre):
        raise AgenteDesconocido(
            f"Nombre de agente inválido: {nombre!r}. Usa minúsculas, números y guion bajo."
        )
    try:
        return importlib.import_module(f"src.{nombre}.graph")
    except ModuleNotFoundError as exc:
        if exc.name in {f"src.{nombre}", f"src.{nombre}.graph"}:
            disponibles = ", ".join(nombres_disponibles()) or "(ninguno)"
            raise AgenteDesconocido(
                f"No existe el agente {nombre!r}. Disponibles: {disponibles}."
            ) from exc
        raise


__all__ = ["AgenteDesconocido", "cargar_agente", "nombres_disponibles"]
