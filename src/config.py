"""Configuración del proyecto leída desde variables de entorno (.env)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent

# Carga .env si existe; las variables ya definidas en el sistema tienen prioridad.
load_dotenv(RAIZ / ".env")


def _texto(nombre: str, por_defecto: str = "") -> str:
    return (os.getenv(nombre) or por_defecto).strip()


class Ajustes:
    """Valores de configuración. Nunca contiene claves reales escritas en el código."""

    def __init__(self) -> None:
        self.google_api_key: str = _texto("GOOGLE_API_KEY")
        self.modelo: str = _texto("MODELO", "gemini-3.5-flash-lite")
        self.telegram_token: str = _texto("TELEGRAM_TOKEN")
        self.telegram_secret: str = _texto("TELEGRAM_SECRET", "cambiame")
        self.public_url: str = _texto("PUBLIC_URL").rstrip("/")

    def exigir_api_key(self) -> str:
        """Devuelve la clave de Google o falla con un mensaje accionable."""
        if not self.google_api_key:
            raise RuntimeError(
                "Falta GOOGLE_API_KEY. Copia .env.example a .env y pega tu clave de Google AI Studio."
            )
        return self.google_api_key

    @property
    def telegram_configurado(self) -> bool:
        return bool(self.telegram_token)

    def __repr__(self) -> str:  # evita filtrar secretos en logs
        return (
            f"Ajustes(modelo={self.modelo!r}, telegram_configurado={self.telegram_configurado}, "
            f"public_url={self.public_url!r})"
        )


ajustes = Ajustes()
