"""Pruebas del agente `asistente` (no llaman al modelo)."""

from __future__ import annotations

import pytest

from src.agentes import AgenteDesconocido, cargar_agente, nombres_disponibles


def test_agente_disponible() -> None:
    assert "asistente" in nombres_disponibles()


def test_grafo_expone_nodos() -> None:
    modulo = cargar_agente("asistente")
    mermaid = modulo.grafo.get_graph().draw_mermaid()
    assert "clasificar" in mermaid
    assert "responder" in mermaid


def test_nombre_invalido() -> None:
    with pytest.raises(AgenteDesconocido):
        cargar_agente("../secreto")


def test_agente_inexistente() -> None:
    with pytest.raises(AgenteDesconocido):
        cargar_agente("no_existe")


def test_prompts_por_nodo() -> None:
    from src.asistente.prompts import PROMPTS

    assert {"clasificar", "responder"} <= set(PROMPTS)
    assert all(texto.strip() for texto in PROMPTS.values())
