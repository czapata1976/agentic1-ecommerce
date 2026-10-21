"""Grafo del agente `router`.

Solo estructura: estado, nodos y aristas. Los textos de cada nodo viven en prompts.py.
"""

from __future__ import annotations

from collections.abc import Hashable
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.llm import crear_llm

from .prompts import PROMPTS


class Decision(BaseModel):
    """Salida estructurada del nodo router."""

    ruta: Literal["preventa", "postventa", "generica"] = Field(
        description="A qué agente va el mensaje."
    )
    motivo: str = Field(description="Una frase: por qué esa ruta.")


class Estado(TypedDict, total=False):
    """Estado compartido entre los nodos del grafo."""

    mensaje: str
    ruta: str
    motivo: str
    respuesta: str
    messages: Annotated[list[AnyMessage], add_messages]


#: Nodo destino para cada ruta.
DESTINOS: dict[Hashable, str] = {
    "preventa": "agente_preventa",
    "postventa": "agente_postventa",
    "generica": "respuesta_generica",
}


def nodo_router(state: Estado) -> dict[str, object]:
    """Clasifica el mensaje con salida estructurada y guarda la decisión."""
    llm = crear_llm(temperatura=0.0).with_structured_output(Decision)
    entrada = HumanMessage(content=state.get("mensaje", ""))
    historial = list(state.get("messages") or [])
    decision = Decision.model_validate(
        llm.invoke([SystemMessage(content=PROMPTS["router"]), *historial, entrada])
    )
    return {
        "ruta": decision.ruta,
        "motivo": decision.motivo,
        "messages": [entrada],
    }


def nodo_agente_preventa(state: Estado) -> dict[str, object]:
    """Cascarón del agente de preventa."""
    texto = PROMPTS["agente_preventa"].format(mensaje=state.get("mensaje", ""))
    return {"respuesta": texto, "messages": [AIMessage(content=texto)]}


def nodo_agente_postventa(state: Estado) -> dict[str, object]:
    """Cascarón del agente de postventa."""
    texto = PROMPTS["agente_postventa"].format(mensaje=state.get("mensaje", ""))
    return {"respuesta": texto, "messages": [AIMessage(content=texto)]}


def nodo_respuesta_generica(state: Estado) -> dict[str, object]:
    """Cascarón para mensajes ajenos a la tienda (sin modelo)."""
    texto = PROMPTS["respuesta_generica"]
    return {"respuesta": texto, "messages": [AIMessage(content=texto)]}


def elegir_destino(state: Estado) -> str:
    """Arista condicional: devuelve la ruta decidida por el router."""
    return state.get("ruta", "generica")


def construir_grafo():
    """Crea y compila el grafo con memoria por thread_id."""
    grafo = StateGraph(Estado)
    grafo.add_node("router", nodo_router)
    grafo.add_node("agente_preventa", nodo_agente_preventa)
    grafo.add_node("agente_postventa", nodo_agente_postventa)
    grafo.add_node("respuesta_generica", nodo_respuesta_generica)

    grafo.add_edge(START, "router")
    grafo.add_conditional_edges("router", elegir_destino, DESTINOS)
    for destino in DESTINOS.values():
        grafo.add_edge(destino, END)

    return grafo.compile(checkpointer=MemorySaver())


#: Instancia que consumen main.py y la API.
grafo = construir_grafo()
