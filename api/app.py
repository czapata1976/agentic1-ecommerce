"""API FastAPI del proyecto: router de un ecommerce.

Levantar en local:
    uvicorn api.app:app --reload --port 8000
Documentación interactiva: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Literal

import httpx
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Security,
)
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field

from src.config import ajustes

# El grafo se importa (y por tanto se compila) UNA sola vez al arrancar la app.
from src.router.graph import grafo as grafo_router

# uvicorn configura sus loggers, no el raíz: `api.router` recibe un handler propio
# para que sus INFO salgan en `heroku logs --tail`.
# OJO: no se activa INFO en el raíz a propósito. El logger de httpx registra la
# URL de cada petición, y la de sendMessage lleva el token del bot.
registro = logging.getLogger("api.router")
registro.setLevel(logging.INFO)
if not registro.handlers:
    _manejador = logging.StreamHandler()
    _manejador.setFormatter(logging.Formatter("%(levelname)s:%(name)s: %(message)s"))
    registro.addHandler(_manejador)
registro.propagate = False

# --- Seguridad de /chat ---------------------------------------------------
# Si API_KEY tiene valor, /chat exige la cabecera X-API-Key. Si está vacía, la
# protección se desactiva (útil para pruebas locales).
# /telegram NO usa esta clave: se autentica con X-Telegram-Bot-Api-Secret-Token.
esquema_api_key = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clave definida en la variable API_KEY. Si está vacía, /chat no la pide.",
)


def verificar_api_key(clave: str | None = Security(esquema_api_key)) -> None:
    """Exige una API key válida cuando la variable API_KEY no está vacía."""
    if not ajustes.api_key:
        return
    if not clave or not secrets.compare_digest(clave, ajustes.api_key):
        registro.warning("Petición rechazada: API key ausente o incorrecta.")
        raise HTTPException(status_code=401, detail="API key ausente o incorrecta.")

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
        {"name": "telegram", "description": "Webhook de Telegram (oculto del Swagger a propósito)."},
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


def _responder_en_telegram(texto: str, chat_id: str) -> str:
    """Enruta el mensaje y devuelve la respuesta para el usuario.

    Cualquier fallo del modelo se queda en el log y se traduce en un mensaje
    genérico: el webhook nunca debe reventar por culpa del LLM.
    """
    try:
        estado = grafo_router.invoke(
            {"mensaje": texto},
            config={"configurable": {"thread_id": chat_id}},
        )
    except Exception:
        registro.exception("Fallo el grafo en el webhook (chat_id=%s)", chat_id)
        return MENSAJE_ERROR_MODELO

    ruta = str(estado.get("ruta", "")).strip()
    motivo = str(estado.get("motivo", "")).strip()
    # Esta línea es la que se revisa con `heroku logs --tail`.
    registro.info("chat_id=%s ruta=%s motivo=%s", chat_id, ruta, motivo)
    return str(estado.get("respuesta", "")).strip() or MENSAJE_ERROR_MODELO


def _enviar_a_telegram(chat_id: int | str, texto: str) -> bool:
    """Envía `texto` al chat con sendMessage (httpx, sin librerías de bot).

    Nunca se registra la excepción completa: su mensaje incluye la URL con el token.
    """
    if not ajustes.telegram_configurado:
        registro.warning("TELEGRAM_TOKEN vacío: no se envía la respuesta a Telegram.")
        return False

    endpoint = f"https://api.telegram.org/bot{ajustes.telegram_token}/sendMessage"
    try:
        respuesta = httpx.post(
            endpoint,
            json={"chat_id": chat_id, "text": texto},
            timeout=20.0,
        )
        respuesta.raise_for_status()
    except httpx.HTTPError as exc:
        detalle = getattr(exc, "response", None)
        registro.error(
            "No se pudo enviar el mensaje a Telegram (chat_id=%s, %s, http=%s): %s",
            chat_id,
            type(exc).__name__,
            getattr(detalle, "status_code", "sin respuesta"),
            getattr(detalle, "text", "")[:200],
        )
        return False
    return True


def _atender_update(texto: str, chat_id: int | str) -> None:
    """Enruta el mensaje y contesta al usuario. Corre en segundo plano."""
    respuesta = _responder_en_telegram(texto, str(chat_id))
    _enviar_a_telegram(chat_id, respuesta)


@app.get("/", include_in_schema=False)
def raiz() -> RedirectResponse:
    """La raíz no tiene contenido propio: se redirige al Swagger."""
    return RedirectResponse(url="/docs")


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
        "elegida, el motivo y la respuesta del agente destino. Si `API_KEY` está "
        "definida, exige la cabecera `X-API-Key`."
    ),
    dependencies=[Depends(verificar_api_key)],
    responses={
        200: {"description": "El router eligió una ruta y respondió."},
        401: {
            "description": (
                "Falta la cabecera `X-API-Key` o no coincide con `API_KEY`."
            )
        },
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
def telegram(
    tareas: BackgroundTasks,
    update: Any = Body(default=None),
    x_telegram_bot_api_secret_token: str = Header(default=""),
) -> dict[str, bool]:
    """Webhook de Telegram: valida el secreto, encola la respuesta y devuelve 200.

    Contesta al instante y deja el enrutamiento y el `sendMessage` en segundo
    plano: si el modelo tarda, Telegram ya recibió su 200 y no reintenta el
    update (el usuario no recibe la respuesta dos veces). El único caso que no
    devuelve 200 es el 403 por secreto inválido.
    """
    if not secrets.compare_digest(
        x_telegram_bot_api_secret_token, ajustes.telegram_secret
    ):
        registro.warning("Webhook rechazado: el secreto de la cabecera no coincide.")
        raise HTTPException(status_code=403, detail="Secreto de Telegram inválido.")

    if not isinstance(update, dict):
        return {"ok": True}

    mensaje = update.get("message")
    if not isinstance(mensaje, dict):
        return {"ok": True}  # edited_message, callback_query, etc.

    chat = mensaje.get("chat")
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    texto = str(mensaje.get("text") or "").strip()
    if chat_id is None or not texto:
        return {"ok": True}  # fotos, stickers o audios: no hay texto que enrutar

    # Se responde 200 ya y el trabajo pesado sigue en segundo plano.
    tareas.add_task(_atender_update, texto, chat_id)
    return {"ok": True}
