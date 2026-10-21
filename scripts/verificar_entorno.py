"""Revisa que el entorno esté listo antes de ejecutar agentes o la API.

Uso:
    python scripts/verificar_entorno.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.agentes import nombres_disponibles  # noqa: E402
from src.config import ajustes  # noqa: E402


def main() -> int:
    problemas: list[str] = []

    if not (RAIZ / ".env").is_file():
        problemas.append("No existe .env (copia .env.example y rellena los valores).")
    if not ajustes.google_api_key:
        problemas.append("GOOGLE_API_KEY está vacía.")
    if not ajustes.telegram_token:
        print("[aviso] TELEGRAM_TOKEN vacío: el webhook no enviará mensajes (paso 5).")
    if not ajustes.public_url:
        print("[aviso] PUBLIC_URL vacía: se completa al desplegar en Heroku.")
    if ajustes.telegram_secret == "cambiame":
        print("[aviso] TELEGRAM_SECRET sigue en el valor por defecto.")

    print(f"Modelo: {ajustes.modelo}")
    print(f"Agentes: {', '.join(nombres_disponibles()) or '(ninguno)'}")

    for problema in problemas:
        print(f"[error] {problema}")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
