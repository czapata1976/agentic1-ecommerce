"""Grafo del agente `asistente`.

Solo estructura: estado, nodos y aristas. Los textos de cada nodo viven en prompts.py.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from src.config import ajustes
from src.llm import crear_llm

from .prompts import PROMPTS
from .tools import HERRAMIENTAS


class Estado(TypedDict, total=False):
    """Estado compartido entre los nodos del grafo."""

    mensaje: str
    tema: str
    respuesta: str


POR_NOMBRE = {herramienta.name: herramienta for herramienta in HERRAMIENTAS}
MAX_PASOS_HERRAMIENTAS = 4


def _texto(contenido: Any) -> str:
    """Normaliza el contenido devuelto por el LLM (str o lista de bloques)."""
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        partes = [
            bloque.get("text", "") if isinstance(bloque, dict) else str(bloque)
            for bloque in contenido
        ]
        return "".join(partes)
    return str(contenido)


def nodo_clasificar(estado: Estado) -> dict[str, str]:
    """Etiqueta el mensaje del usuario con una llamada corta al modelo."""
    llm = crear_llm(temperatura=0.0)
    salida = llm.invoke(
        [
            SystemMessage(content=PROMPTS["clasificar"]),
            HumanMessage(content=estado["mensaje"]),
        ]
    )
    tema = _texto(salida.content).strip().lower()[:60]
    return {"tema": tema or "otro"}


def nodo_responder(estado: Estado) -> dict[str, str]:
    """Genera la respuesta final, resolviendo llamadas a herramientas si las hay."""
    llm = crear_llm(temperatura=0.3).bind_tools(HERRAMIENTAS)
    mensajes: list[Any] = [
        SystemMessage(
            content=PROMPTS["responder"].format(
                modelo=ajustes.modelo, tema=estado.get("tema", "otro")
            )
        ),
        HumanMessage(content=estado["mensaje"]),
    ]

    respuesta: Any = None
    for _ in range(MAX_PASOS_HERRAMIENTAS):
        respuesta = llm.invoke(mensajes)
        llamadas = getattr(respuesta, "tool_calls", None) or []
        if not llamadas:
            return {"respuesta": _texto(respuesta.content).strip()}

        mensajes.append(respuesta)
        for llamada in llamadas:
            herramienta = POR_NOMBRE.get(llamada["name"])
            try:
                salida = (
                    herramienta.invoke(llamada["args"])
                    if herramienta
                    else f"Herramienta desconocida: {llamada['name']}"
                )
            except Exception as exc:  # noqa: BLE001 - se informa al modelo
                salida = f"Error al ejecutar {llamada['name']}: {exc}"
            mensajes.append(ToolMessage(content=str(salida), tool_call_id=llamada["id"]))

    texto = _texto(getattr(respuesta, "content", "")).strip()
    return {"respuesta": texto or "No pude completar la respuesta en este intento."}


def construir_grafo():
    """Crea y compila el grafo del agente."""
    grafo = StateGraph(Estado)
    grafo.add_node("clasificar", nodo_clasificar)
    grafo.add_node("responder", nodo_responder)
    grafo.add_edge(START, "clasificar")
    grafo.add_edge("clasificar", "responder")
    grafo.add_edge("responder", END)
    return grafo.compile()


#: Instancia que consumen main.py y la API.
grafo = construir_grafo()
