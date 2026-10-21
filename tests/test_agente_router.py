"""Pruebas del agente `router` (sin llamar al modelo real)."""

from __future__ import annotations

import pytest

from src.agentes import cargar_agente, nombres_disponibles
from src.router import graph as grafo_mod
from src.router.graph import Decision


class _LLMFalso:
    """Sustituye a crear_llm(): devuelve siempre la misma decisión."""

    def __init__(self, decision: Decision) -> None:
        self.decision = decision

    def with_structured_output(self, schema: type) -> "_LLMFalso":
        return self

    def invoke(self, mensajes):  # noqa: ANN001
        return self.decision


def test_router_disponible() -> None:
    assert "router" in nombres_disponibles()


def test_grafo_dibuja_router_y_destinos() -> None:
    modulo = cargar_agente("router")
    mermaid = modulo.grafo.get_graph().draw_mermaid()
    for nodo in ("router", "agente_preventa", "agente_postventa", "respuesta_generica"):
        assert nodo in mermaid


def test_prompts_por_nodo() -> None:
    from src.router.prompts import PROMPTS

    assert set(PROMPTS) == {
        "router",
        "agente_preventa",
        "agente_postventa",
        "respuesta_generica",
    }
    assert all(texto.strip() for texto in PROMPTS.values())


def test_cascaron_generico_sin_modelo() -> None:
    estado = grafo_mod.nodo_respuesta_generica({"mensaje": "¿qué hora es en Tokio?"})
    assert "tienda" in estado["respuesta"]
    assert estado["messages"][0].content == estado["respuesta"]


@pytest.mark.parametrize(
    ("ruta", "nodo"),
    [
        ("preventa", "agente_preventa"),
        ("postventa", "agente_postventa"),
        ("generica", "respuesta_generica"),
    ],
)
def test_enruta_al_nodo_correcto(
    monkeypatch: pytest.MonkeyPatch, ruta: str, nodo: str
) -> None:
    decision = Decision(ruta=ruta, motivo=f"motivo de prueba para {ruta}")  # type: ignore[arg-type]
    monkeypatch.setattr(grafo_mod, "crear_llm", lambda temperatura=0.0: _LLMFalso(decision))

    resultado = grafo_mod.grafo.invoke(
        {"mensaje": "mensaje de prueba"},
        config={"configurable": {"thread_id": f"test-{ruta}"}},
    )

    assert resultado["ruta"] == ruta
    assert resultado["motivo"] == decision.motivo
    assert resultado["respuesta"]
    assert any(mensaje.content == "mensaje de prueba" for mensaje in resultado["messages"])
