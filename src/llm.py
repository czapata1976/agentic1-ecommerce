"""Fábrica del modelo de lenguaje (Gemini vía langchain-google-genai)."""

from __future__ import annotations

import warnings

from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import ajustes

# Algunos modelos (p. ej. *-flash-lite) ignoran `temperature`; el aviso es solo informativo.
warnings.filterwarnings(
    "ignore", message=r".*fixed sampling defaults.*", category=UserWarning
)


def crear_llm(temperatura: float = 0.2) -> ChatGoogleGenerativeAI:
    """Crea el LLM. Se instancia dentro de los nodos para que el resto funcione sin clave."""
    return ChatGoogleGenerativeAI(
        model=ajustes.modelo,
        google_api_key=ajustes.exigir_api_key(),
        temperature=temperatura,
    )


__all__ = ["crear_llm"]
