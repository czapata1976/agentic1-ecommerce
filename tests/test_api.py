"""Pruebas de la API del router (sin llamar al modelo real)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.app as api_mod
from api.app import app
from src.config import ajustes

cliente = TestClient(app)


class _GrafoFalso:
    """Sustituye al grafo compilado para capturar la entrada y el thread_id."""

    def __init__(self, resultado: dict[str, Any] | None = None, error: Exception | None = None):
        self.resultado = resultado or {
            "ruta": "preventa",
            "motivo": "motivo de prueba",
            "respuesta": "respuesta de prueba",
        }
        self.error = error
        self.entrada: dict[str, Any] = {}
        self.config: dict[str, Any] = {}

    def invoke(self, entrada: dict[str, Any], config: dict[str, Any] | None = None):
        self.entrada = entrada
        self.config = config or {}
        if self.error:
            raise self.error
        return self.resultado


def test_health() -> None:
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True, "modelo": ajustes.modelo}


@pytest.mark.parametrize("ruta", ["preventa", "postventa", "generica"])
def test_chat_devuelve_ruta_motivo_y_respuesta(
    monkeypatch: pytest.MonkeyPatch, ruta: str
) -> None:
    falso = _GrafoFalso(
        {"ruta": ruta, "motivo": f"motivo {ruta}", "respuesta": f"respuesta {ruta}"}
    )
    monkeypatch.setattr(api_mod, "grafo_router", falso)

    respuesta = cliente.post("/chat", json={"user_id": "cliente-1", "texto": "hola"})

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "ruta": ruta,
        "motivo": f"motivo {ruta}",
        "respuesta": f"respuesta {ruta}",
    }


def test_chat_usa_user_id_como_thread_id(monkeypatch: pytest.MonkeyPatch) -> None:
    falso = _GrafoFalso()
    monkeypatch.setattr(api_mod, "grafo_router", falso)

    cliente.post("/chat", json={"user_id": "cliente-99", "texto": "mi pedido llegó roto"})

    assert falso.entrada == {"mensaje": "mi pedido llegó roto"}
    assert falso.config == {"configurable": {"thread_id": "cliente-99"}}


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"user_id": "cliente-1"},
        {"texto": "hola"},
        {"user_id": "cliente-1", "texto": ""},
        {},
    ],
)
def test_chat_body_invalido_422(cuerpo: dict[str, Any]) -> None:
    assert cliente.post("/chat", json=cuerpo).status_code == 422


def test_chat_falla_el_modelo_502(monkeypatch: pytest.MonkeyPatch) -> None:
    falso = _GrafoFalso(error=RuntimeError("detalle interno con api_key=secreta"))
    monkeypatch.setattr(api_mod, "grafo_router", falso)

    respuesta = cliente.post("/chat", json={"user_id": "cliente-1", "texto": "hola"})

    assert respuesta.status_code == 502
    detalle = respuesta.json()["detail"]
    assert "modelo" in detalle.lower()
    assert "secreta" not in detalle
    assert "Traceback" not in detalle


def test_chat_ruta_inesperada_502(monkeypatch: pytest.MonkeyPatch) -> None:
    falso = _GrafoFalso({"ruta": "otra", "motivo": "x", "respuesta": "y"})
    monkeypatch.setattr(api_mod, "grafo_router", falso)

    assert cliente.post("/chat", json={"user_id": "1", "texto": "hola"}).status_code == 502


def test_telegram_no_expuesto_y_responde_ok() -> None:
    respuesta = cliente.post("/telegram", json={"update_id": 1, "message": {"text": "hola"}})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    assert "/telegram" not in cliente.get("/openapi.json").json()["paths"]


def test_openapi_completo() -> None:
    esquema = cliente.get("/openapi.json").json()

    assert esquema["info"]["title"] == "Ecommerce Router API"
    assert esquema["info"]["version"] == "1.0.0"
    assert "preventa" in esquema["info"]["description"]
    assert {tag["name"] for tag in esquema["tags"]} == {"salud", "chat", "telegram"}

    respuestas = esquema["paths"]["/chat"]["post"]["responses"]
    assert {"200", "422", "502"} <= set(respuestas)

    esquemas = esquema["components"]["schemas"]
    assert esquemas["ChatRequest"]["example"] == {
        "user_id": "cliente-123",
        "texto": "¿tienen la polera azul en talla M?",
    }
    assert "example" in esquemas["ChatResponse"]
    for campo in ("user_id", "texto"):
        assert esquemas["ChatRequest"]["properties"][campo]["description"]
        assert esquemas["ChatRequest"]["properties"][campo]["examples"]
    for campo in ("ruta", "motivo", "respuesta"):
        assert esquemas["ChatResponse"]["properties"][campo]["description"]
        assert esquemas["ChatResponse"]["properties"][campo]["examples"]
