"""Muestra el estado del webhook de Telegram (getWebhookInfo).

Uso:
    python scripts/webhook_info.py

Sirve para confirmar que el webhook quedó apuntando a PUBLIC_URL + "/telegram"
y para ver si Telegram tiene updates pendientes o un último error registrado.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import ajustes  # noqa: E402


def _fecha(marca: Any) -> str:
    """Convierte el timestamp de Telegram en una fecha legible."""
    try:
        return datetime.fromtimestamp(int(marca)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return "-"


def main() -> int:
    if not ajustes.telegram_token:
        print("[error] TELEGRAM_TOKEN está vacío: créalo con @BotFather (/newbot).")
        return 1

    endpoint = f"https://api.telegram.org/bot{ajustes.telegram_token}/getWebhookInfo"
    try:
        respuesta = httpx.get(endpoint, timeout=20.0)
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (httpx.HTTPError, ValueError) as exc:
        # Sin la excepción completa: su mensaje incluye la URL con el token.
        detalle = getattr(getattr(exc, "response", None), "text", "")[:300]
        print(f"[error] No se pudo consultar getWebhookInfo ({type(exc).__name__}): {detalle}")
        return 1

    if not datos.get("ok"):
        print(f"[error] Telegram respondió: {datos}")
        return 1

    info = datos.get("result") or {}
    url = info.get("url") or ""
    pendientes = int(info.get("pending_update_count") or 0)
    ultimo_error = info.get("last_error_message") or ""

    print(f"url:                 {url or '(sin webhook registrado)'}")
    print(f"pending_update_count: {pendientes}")
    print(f"last_error_date:     {_fecha(info.get('last_error_date'))}")
    print(f"last_error_message:  {ultimo_error or '-'}")
    print(f"max_connections:     {info.get('max_connections', '-')}")
    print(f"ip_address:          {info.get('ip_address', '-')}")

    esperado = f"{ajustes.public_url}/telegram" if ajustes.public_url else ""
    problemas = False

    if not url:
        print("[aviso] No hay webhook: ejecuta python scripts/set_webhook.py.")
        problemas = True
    elif esperado and url != esperado:
        print(f"[aviso] El webhook apunta a otra URL. Se esperaba: {esperado}")
        problemas = True
    if ultimo_error:
        print(f"[aviso] Último error de Telegram: {ultimo_error}")
        problemas = True
    if pendientes:
        print(f"[aviso] Hay {pendientes} update(s) sin entregar: revisa que la API esté arriba.")
        problemas = True

    print("\nWebhook OK." if not problemas else "\nHay cosas que revisar (ver avisos).")
    return 0 if not problemas else 1


if __name__ == "__main__":
    raise SystemExit(main())
