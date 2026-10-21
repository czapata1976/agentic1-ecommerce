"""Herramientas del agente `asistente`."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool


@tool
def hora_actual(zona: str = "America/Bogota") -> str:
    """Devuelve la fecha y hora actuales en la zona horaria IANA indicada."""
    return datetime.now(ZoneInfo(zona)).strftime("%Y-%m-%d %H:%M:%S %Z")


@tool
def contar_palabras(texto: str) -> str:
    """Cuenta cuántas palabras tiene el texto recibido."""
    return str(len(texto.split()))


HERRAMIENTAS = [hora_actual, contar_palabras]
