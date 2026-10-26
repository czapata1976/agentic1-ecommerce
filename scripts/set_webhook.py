"""Registra el webhook de Telegram apuntando a la API desplegada.

Uso:
    python scripts/set_webhook.py

Toma PUBLIC_URL, TELEGRAM_TOKEN y TELEGRAM_SECRET del entorno o de .env.
Antes de ejecutarlo, la API tiene que estar publicada en esa URL https
(Heroku o un túnel de cloudflared) y haber sido desplegada con estos cambios.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.config import ajustes  # noqa: E402


def main() -> int:
    if not ajustes.telegram_token:
        print("[error] TELEGRAM_TOKEN está vacío: créalo con @BotFather (/newbot).")
        return 1
    if not ajustes.public_url:
        print("[error] PUBLIC_URL está vacía: usa la URL https de Heroku o de cloudflared.")
        return 1
    if not ajustes.public_url.startswith("https://"):
        print(f"[error] PUBLIC_URL debe empezar con https:// (vale: {ajustes.public_url}).")
        return 1

    url_webhook = f"{ajustes.public_url}/telegram"
    endpoint = f"https://api.telegram.org/bot{ajustes.telegram_token}/setWebhook"

    try:
        respuesta = httpx.post(
            endpoint,
            json={"url": url_webhook, "secret_token": ajustes.telegram_secret},
            timeout=20.0,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as exc:
        # No se imprime la excepción: su mensaje incluye la URL, que lleva el token.
        detalle = getattr(getattr(exc, "response", None), "text", "")[:300]
        print(f"[error] Telegram rechazó setWebhook ({type(exc).__name__}): {detalle}")
        return 1

    print(f"Webhook registrado: {url_webhook}")
    print(f"Respuesta de Telegram: {respuesta.text}")
    print("Comprueba el estado con: python scripts/webhook_info.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
