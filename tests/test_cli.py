"""Prueba de la CLI: --diagrama funciona sin clave de API."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_diagrama_sin_ejecutar_grafo() -> None:
    resultado = subprocess.run(
        [sys.executable, "main.py", "asistente", "--diagrama"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "graph TD" in resultado.stdout
    assert "responder" in resultado.stdout
