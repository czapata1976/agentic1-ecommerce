"""API FastAPI del proyecto: router de un ecommerce.

Levantar en local:
    uvicorn api.app:app --reload --port 8000
Documentación interactiva: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.config import ajustes

# El grafo se importa (y por tanto se compila) UNA sola vez al arrancar la app.
from src.router.graph import grafo as grafo_router

registro = logging.getLogger("api.router")

DESCRIPCION = """
API HTTP del **router** de un ecommerce, construido con LangGraph.

Recibe el mensaje de un cliente, decide a qué agente enviarlo y devuelve la
respuesta de ese agente. La decisión se guarda en memoria por `user_id`
(se usa como `thread_id` del grafo).

Rutas posibles:

- **preventa**: intención de compra, productos, precios, tallas, stock, promociones y formas de pago.
- **postventa**: quejas, reclamos, seguimiento de pedidos, devoluciones, cambios y garantía.
- **generica**: mensajes ajenos a la tienda o saludos sin pedido.
"""

app = FastAPI(
    title="Ecommerce Router API",
    version="1.0.0",
    description=DESCRIPCION,
    openapi_tags=[
        {"name": "salud", "description": "Estado del servicio y modelo configurado."},
        {"name": "chat", "description": "Enrutamiento de mensajes de clientes."},
        {"name": "telegram", "description": "Webhook de Telegram (pendiente, parte 5)."},
    ],
)

RUTAS = ("preventa", "postventa", "generica")
MENSAJE_ERROR_MODELO = (
    "El modelo no pudo procesar el mensaje. Intenta nuevamente en unos segundos."
)


class HealthResponse(BaseModel):
    """Estado del servicio."""

    ok: bool = Field(..., description="true si la API está operativa.", examples=[True])
    modelo: str = Field(
        ...,
        description="Modelo de Gemini configurado en la variable MODELO.",
        examples=["gemini-3.5-flash-lite"],
    )


class ChatRequest(BaseModel):
    """Mensaje que escribe un cliente en el chat."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "cliente-123",
                "texto": "¿tienen la polera azul en talla M?",
            }
        }
    )

    user_id: str = Field(
        ...,
        min_length=1,
        description="Identificador del usuario. Se usa como thread_id de la memoria.",
        examples=["cliente-123"],
    )
    texto: str = Field(
        ...,
        min_length=1,
        description="Mensaje escrito por el cliente. Obligatorio y no vacío.",
        examples=["¿tienen la polera azul en talla M?"],
    )


class ChatResponse(BaseModel):
    """Decisión del router y respuesta del agente elegido."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ruta": "preventa",
                "motivo": "El cliente pregunta por tallas y stock antes de comprar.",
                "respuesta": (
                    "Soy el agente de preventa. Recibí: ¿tienen la polera azul en talla M?. "
                    "Pronto podré ayudarte con productos y compras."
                ),
            }
        }
    )

    ruta: Literal["preventa", "postventa", "generica"] = Field(
        ...,
        description="Agente que atendió el mensaje.",
        examples=["preventa"],
    )
    motivo: str = Field(
        ...,
        description="Una frase que explica por qué se eligió esa ruta.",
        examples=["El cliente pregunta por tallas y stock antes de comprar."],
    )
    respuesta: str = Field(
        ...,
        description="Respuesta del agente elegido.",
        examples=["Soy el agente de preventa. Recibí: ... Pronto podré ayudarte."],
    )


def _invocar_router(user_id: str, texto: str) -> ChatResponse:
    """Ejecuta el grafo ya compilado usando `user_id` como thread_id."""
    try:
        estado = grafo_router.invoke(
            {"mensaje": texto},
            config={"configurable": {"thread_id": user_id}},
        )
    except Exception:
        # El detalle y el stack quedan SOLO en el log del servidor; al cliente no se exponen.
        registro.exception("Fallo el grafo router (user_id=%s)", user_id)
        raise HTTPException(status_code=502, detail=MENSAJE_ERROR_MODELO) from None

    ruta = estado.get("ruta")
    if ruta not in RUTAS:
        registro.error("Ruta inesperada devuelta por el grafo: %r", ruta)
        raise HTTPException(status_code=502, detail=MENSAJE_ERROR_MODELO)

    return ChatResponse(
        ruta=ruta,
        motivo=str(estado.get("motivo", "")).strip(),
        respuesta=str(estado.get("respuesta", "")).strip(),
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["salud"],
    summary="Estado del servicio",
    description="Comprueba que la API responde y muestra el modelo configurado.",
)
def health() -> HealthResponse:
    return HealthResponse(ok=True, modelo=ajustes.modelo)


@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["chat"],
    summary="Enruta un mensaje de cliente",
    description=(
        "Invoca el grafo `router` con `user_id` como `thread_id` y devuelve la ruta "
        "elegida, el motivo y la respuesta del agente destino."
    ),
    responses={
        200: {"description": "El router eligió una ruta y respondió."},
        422: {
            "description": (
                "Body inválido: falta `user_id` o `texto`, o alguno viene vacío."
            )
        },
        502: {
            "description": (
                "El modelo falló al procesar el mensaje. El detalle queda en el log "
                "del servidor."
            )
        },
    },
)
def chat(peticion: ChatRequest) -> ChatResponse:
    return _invocar_router(user_id=peticion.user_id, texto=peticion.texto)


@app.post("/telegram", include_in_schema=False)
def telegram(payload: Any = Body(default=None)) -> dict[str, bool]:
    """Webhook de Telegram. Se implementa en la parte 5 del taller."""
    return {"ok": True}
