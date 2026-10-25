"""Corre los casos de `tests/casos_router.json` contra el agente `router`.

Imprime una tabla con mensaje, esperado, obtenido, ✔/✘ y el motivo que dio el
router, y termina con el resumen de aciertos y la lista de los fallados.

Uso:
    python scripts/test_router.py

Código de salida: 0 si logra al menos MINIMO_ACEPTADO aciertos, 1 si no,
2 si hay un error de configuración (JSON inválido, falta GOOGLE_API_KEY, etc.).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.agentes import cargar_agente  # noqa: E402

try:  # error del proveedor: cuota agotada, clave inválida, red caída...
    from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
except ImportError:  # pragma: no cover - la ruta cambió entre versiones
    ChatGoogleGenerativeAIError = RuntimeError  # type: ignore[assignment, misc]

RUTA_CASOS = RAIZ / "tests" / "casos_router.json"
AGENTE = "router"
MINIMO_ACEPTADO = 13
ANCHO_MENSAJE = 46
ANCHO_MOTIVO = 48


@dataclass(frozen=True)
class Resultado:
    """Resultado de un caso: lo esperado, lo obtenido y el motivo del router."""

    numero: int
    mensaje: str
    esperado: str
    obtenido: str
    motivo: str

    @property
    def acertado(self) -> bool:
        return self.obtenido == self.esperado


def _forzar_utf8() -> None:
    """La consola de Windows en español usa cp1252 y no puede con ✔/✘."""
    salida = getattr(sys.stdout, "reconfigure", None)
    if salida is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # consola que no permite reconfigurarse
            pass


def cargar_casos(ruta: Path = RUTA_CASOS) -> list[dict[str, str]]:
    """Lee el JSON y valida que cada caso traiga `mensaje` y `esperado`."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, list) or not datos:
        raise ValueError(f"{ruta} debe contener una lista de casos no vacía")

    casos: list[dict[str, str]] = []
    for posicion, caso in enumerate(datos, start=1):
        if not isinstance(caso, dict) or not {"mensaje", "esperado"} <= set(caso):
            raise ValueError(
                f"Caso {posicion} inválido: se esperaban las claves 'mensaje' y 'esperado'"
            )
        mensaje = str(caso["mensaje"]).strip()
        esperado = str(caso["esperado"]).strip()
        if not mensaje or not esperado:
            raise ValueError(f"Caso {posicion} inválido: 'mensaje' o 'esperado' vacío")
        casos.append({"mensaje": mensaje, "esperado": esperado})
    return casos


def evaluar(grafo: Any, casos: list[dict[str, str]]) -> list[Resultado]:
    """Ejecuta el grafo una vez por caso, con un `thread_id` propio cada vez."""
    resultados: list[Resultado] = []
    for numero, caso in enumerate(casos, start=1):
        estado = grafo.invoke(
            {"mensaje": caso["mensaje"]},
            config={"configurable": {"thread_id": f"script-router-{numero}"}},
        )
        resultados.append(
            Resultado(
                numero=numero,
                mensaje=caso["mensaje"],
                esperado=caso["esperado"],
                obtenido=str(estado.get("ruta") or "?"),
                motivo=str(estado.get("motivo") or "").strip(),
            )
        )
    return resultados


def _recortar(texto: str, ancho: int) -> str:
    """Normaliza espacios y recorta con puntos suspensivos si no cabe."""
    limpio = " ".join(texto.split())
    return limpio if len(limpio) <= ancho else limpio[: ancho - 1] + "…"


def imprimir_tabla(resultados: list[Resultado]) -> None:
    """Imprime la tabla de resultados alineada por columnas."""
    encabezado = ("#", "MENSAJE", "ESPERADO", "OBTENIDO", "OK", "MOTIVO")
    filas = [
        (
            str(r.numero),
            _recortar(r.mensaje, ANCHO_MENSAJE),
            r.esperado,
            r.obtenido,
            "✔" if r.acertado else "✘",
            _recortar(r.motivo, ANCHO_MOTIVO),
        )
        for r in resultados
    ]
    anchos = [
        max(len(fila[columna]) for fila in (encabezado, *filas))
        for columna in range(len(encabezado))
    ]

    def linea(celdas: tuple[str, ...]) -> str:
        return "  ".join(celda.ljust(ancho) for celda, ancho in zip(celdas, anchos)).rstrip()

    print(linea(encabezado))
    print("─" * (sum(anchos) + 2 * (len(anchos) - 1)))
    for fila in filas:
        print(linea(fila))


def imprimir_resumen(resultados: list[Resultado]) -> int:
    """Muestra aciertos, porcentaje y fallados; devuelve el código de salida."""
    if not resultados:
        print("\nNo hay resultados.")
        return 1

    total = len(resultados)
    aciertos = sum(1 for r in resultados if r.acertado)
    fallados = [r for r in resultados if not r.acertado]

    print()
    print(f"Aciertos: {aciertos}/{total} ({100 * aciertos / total:.1f} %)")
    print(f"Mínimo que exige tests/test_router.py: {MINIMO_ACEPTADO}/{total}")

    if not fallados:
        print("Fallados: ninguno.")
        return 0

    print(f"Fallados ({len(fallados)}):")
    for r in fallados:
        print(f'  - [{r.numero}] esperado={r.esperado} obtenido={r.obtenido}: "{r.mensaje}"')
        if r.motivo:
            print(f"    motivo: {r.motivo}")

    return 0 if aciertos >= MINIMO_ACEPTADO else 1


def main() -> int:
    _forzar_utf8()
    try:
        casos = cargar_casos()
        grafo = cargar_agente(AGENTE).grafo
        print(f"Corriendo {len(casos)} casos contra el agente '{AGENTE}'...", flush=True)
        resultados = evaluar(grafo, casos)
    # AgenteDesconocido, JSONDecodeError y las validaciones son ValueError.
    except (OSError, ValueError, RuntimeError, ChatGoogleGenerativeAIError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    imprimir_tabla(resultados)
    return imprimir_resumen(resultados)


if __name__ == "__main__":
    raise SystemExit(main())
