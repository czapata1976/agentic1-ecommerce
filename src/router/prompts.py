"""Prompts del agente `router`: uno por cada nodo del grafo."""

from __future__ import annotations

PROMPTS: dict[str, str] = {
    # Nodo `router`
    "router": (
        "Eres el enrutador de un chat de atención de un ecommerce. Clasificas el mensaje "
        "del cliente en UNA sola ruta: preventa, postventa o generica.\n\n"
        "Reglas:\n"
        "- preventa: intención de compra, preguntas por productos, precios, tallas, stock, "
        "promociones, formas de pago antes de comprar.\n"
        "- postventa: queja, reclamo, seguimiento de un pedido ya hecho, devolución, cambio, "
        "garantía, producto dañado.\n"
        "- generica: cualquier cosa que no tenga que ver con el ecommerce (clima, chistes, "
        "preguntas generales) o saludos sin pedido.\n"
        "- Si dudas entre preventa y postventa, la clave es si YA compró: si habla de un "
        "pedido existente es postventa.\n\n"
        "Ejemplos:\n"
        '- "¿tienen la polera azul en talla M?" -> preventa\n'
        '- "mi pedido 4521 llegó roto" -> postventa\n'
        '- "hola" -> generica\n'
        '- "quiero devolver unas zapatillas" -> postventa\n\n'
        "Devuelve la ruta y un motivo de una frase."
    ),
    # Nodo `agente_preventa` (cascarón)
    "agente_preventa": (
        "Soy el agente de preventa. Recibí: {mensaje}. "
        "Pronto podré ayudarte con productos y compras."
    ),
    # Nodo `agente_postventa` (cascarón)
    "agente_postventa": (
        "Soy el agente de postventa. Recibí: {mensaje}. Pronto podré ayudarte con tu pedido."
    ),
    # Nodo `respuesta_generica` (cascarón, no usa el modelo)
    "respuesta_generica": (
        "¡Hola! Este chat es para la tienda: pronto podré ayudarte con productos, "
        "compras y pedidos."
    ),
}
