"""Pruebas de la API del router (sin llamar al modelo real)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.app as api_mod
from api.app import app
from src.config import ajustes

cliente = TestClient(app)


@pytest.fixture(autouse=True)
def _api_key_vacia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Por defecto las pruebas corren sin API_KEY: protección desactivada."""
    monkeypatch.setattr(api_mod.ajustes, "api_key", "")


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


def test_raiz_redirige_a_docs() -> None:
    respuesta = cliente.get("/", follow_redirects=False)
    assert respuesta.status_code in (307, 308)
    assert respuesta.headers["location"] == "/docs"


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


def test_chat_exige_api_key_cuando_esta_configurada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_mod, "grafo_router", _GrafoFalso())
    monkeypatch.setattr(api_mod.ajustes, "api_key", "clave-de-prueba")
    cuerpo = {"user_id": "cliente-1", "texto": "hola"}

    assert cliente.post("/chat", json=cuerpo).status_code == 401
    assert cliente.post(
        "/chat", json=cuerpo, headers={"X-API-Key": "otra"}
    ).status_code == 401
    assert cliente.post(
        "/chat", json=cuerpo, headers={"X-API-Key": "clave-de-prueba"}
    ).status_code == 200


def test_chat_sin_api_key_configurada_no_pide_cabecera(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api_mod, "grafo_router", _GrafoFalso())
    respuesta = cliente.post("/chat", json={"user_id": "cliente-1", "texto": "hola"})
    assert respuesta.status_code == 200


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


def test_telegram_no_aparece_en_el_swagger() -> None:
    assert "/telegram" not in cliente.get("/openapi.json").json()["paths"]


CABECERA_TELEGRAM = {"X-Telegram-Bot-Api-Secret-Token": ajustes.telegram_secret}


class _RespuestaHTTPFalsa:
    """Imita la respuesta de httpx.post."""

    status_code = 200
    text = '{"ok":true,"result":{"message_id":1}}'

    def raise_for_status(self) -> None:
        return None


@pytest.fixture
def envio_telegram(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura las llamadas a httpx.post para no salir a la red."""
    llamadas: list[dict[str, Any]] = []

    def post_falso(  # noqa: ANN001
        url: str, json: dict[str, Any] | None = None, timeout: float | None = None
    ) -> _RespuestaHTTPFalsa:
        llamadas.append({"url": url, "json": json, "timeout": timeout})
        return _RespuestaHTTPFalsa()

    monkeypatch.setattr(api_mod.httpx, "post", post_falso)
    return llamadas


def test_telegram_sin_secreto_403() -> None:
    respuesta = cliente.post("/telegram", json={"update_id": 1})
    assert respuesta.status_code == 403


def test_telegram_secreto_incorrecto_403() -> None:
    respuesta = cliente.post(
        "/telegram",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "otro-secreto"},
    )
    assert respuesta.status_code == 403


def test_telegram_enruta_y_responde_al_chat(
    monkeypatch: pytest.MonkeyPatch, envio_telegram: list[dict[str, Any]]
) -> None:
    falso = _GrafoFalso()
    monkeypatch.setattr(api_mod, "grafo_router", falso)

    respuesta = cliente.post(
        "/telegram",
        headers=CABECERA_TELEGRAM,
        json={
            "update_id": 1,
            "message": {
                "message_id": 7,
                "text": "mi pedido llegó roto",
                "chat": {"id": 4242},
            },
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    assert falso.entrada == {"mensaje": "mi pedido llegó roto"}
    assert falso.config == {"configurable": {"thread_id": "4242"}}
    assert len(envio_telegram) == 1
    assert envio_telegram[0]["url"].endswith("/sendMessage")
    assert envio_telegram[0]["json"] == {"chat_id": 4242, "text": "respuesta de prueba"}


def test_telegram_ignora_updates_sin_texto(
    monkeypatch: pytest.MonkeyPatch, envio_telegram: list[dict[str, Any]]
) -> None:
    falso = _GrafoFalso()
    monkeypatch.setattr(api_mod, "grafo_router", falso)

    respuesta = cliente.post(
        "/telegram",
        headers=CABECERA_TELEGRAM,
        json={"update_id": 2, "message": {"photo": [{"file_id": "x"}], "chat": {"id": 1}}},
    )

    assert respuesta.status_code == 200
    assert falso.entrada == {}
    assert envio_telegram == []


def test_telegram_sin_token_no_intenta_enviar(
    monkeypatch: pytest.MonkeyPatch, envio_telegram: list[dict[str, Any]]
) -> None:
    monkeypatch.setattr(api_mod, "grafo_router", _GrafoFalso())
    monkeypatch.setattr(api_mod.ajustes, "telegram_token", "")

    respuesta = cliente.post(
        "/telegram",
        headers=CABECERA_TELEGRAM,
        json={"update_id": 4, "message": {"text": "hola", "chat": {"id": 8}}},
    )

    assert respuesta.status_code == 200
    assert envio_telegram == []


def test_telegram_devuelve_200_si_falla_el_modelo(
    monkeypatch: pytest.MonkeyPatch, envio_telegram: list[dict[str, Any]]
) -> None:
    falso = _GrafoFalso(error=RuntimeError("detalle interno con api_key=secreta"))
    monkeypatch.setattr(api_mod, "grafo_router", falso)

    respuesta = cliente.post(
        "/telegram",
        headers=CABECERA_TELEGRAM,
        json={"update_id": 3, "message": {"text": "hola", "chat": {"id": 9}}},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    assert len(envio_telegram) == 1
    texto = envio_telegram[0]["json"]["text"]
    assert "modelo" in texto.lower()
    assert "secreta" not in texto


def test_telegram_no_usa_la_api_key(
    monkeypatch: pytest.MonkeyPatch, envio_telegram: list[dict[str, Any]]
) -> None:
    """El webhook se autentica con su propio secreto, no con X-API-Key."""
    monkeypatch.setattr(api_mod, "grafo_router", _GrafoFalso())
    monkeypatch.setattr(api_mod.ajustes, "api_key", "clave-de-prueba")

    respuesta = cliente.post(
        "/telegram",
        headers=CABECERA_TELEGRAM,
        json={"update_id": 5, "message": {"text": "hola", "chat": {"id": 7}}},
    )

    assert respuesta.status_code == 200
    assert len(envio_telegram) == 1


def test_openapi_completo() -> None:
    esquema = cliente.get("/openapi.json").json()

    assert esquema["info"]["title"] == "Ecommerce Router API"
    assert esquema["info"]["version"] == "1.0.0"
    assert "preventa" in esquema["info"]["description"]
    assert {tag["name"] for tag in esquema["tags"]} == {"salud", "chat", "telegram"}

    respuestas = esquema["paths"]["/chat"]["post"]["responses"]
    assert {"200", "401", "422", "502"} <= set(respuestas)

    esquemas_seguridad = esquema["components"].get("securitySchemes", {})
    assert any(s.get("name") == "X-API-Key" for s in esquemas_seguridad.values())

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
