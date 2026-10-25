"""Pruebas del router con el modelo real.

Corre los 15 casos de `tests/casos_router.json` y exige **al menos 13 aciertos**:
el modelo no es determinista, así que pedir 15 haría la suite inestable.

Cada caso se reporta por separado (un fallo aparece como `xfail`, no rompe la
suite) y `test_minimo_de_aciertos` es el que aplica el umbral real.

Requiere `GOOGLE_API_KEY` en el entorno o en `.env`; sin clave, los casos se
saltan en lugar de fallar.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.agentes import cargar_agente  # noqa: E402
from src.config import ajustes  # noqa: E402

RUTA_CASOS = RAIZ / "tests" / "casos_router.json"
MINIMO_ACERTADOS = 13
CASOS: list[dict[str, str]] = json.loads(RUTA_CASOS.read_text(encoding="utf-8"))

#: Estos casos consumen cuota: se excluyen con `-m "not integracion"`.
pytestmark = pytest.mark.integracion


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


@pytest.fixture(scope="module")
def resultados() -> list[Resultado]:
    """Corre los 15 casos una sola vez y reutiliza la lista en todos los tests."""
    if not ajustes.google_api_key:
        pytest.skip("Falta GOOGLE_API_KEY: estos casos llaman al modelo real.")

    grafo = cargar_agente("router").grafo
    salida: list[Resultado] = []
    for numero, caso in enumerate(CASOS, start=1):
        estado: dict[str, Any] = grafo.invoke(
            {"mensaje": caso["mensaje"]},
            config={"configurable": {"thread_id": f"pytest-router-{numero}"}},
        )
        salida.append(
            Resultado(
                numero=numero,
                mensaje=caso["mensaje"],
                esperado=caso["esperado"],
                obtenido=str(estado.get("ruta") or "?"),
                motivo=str(estado.get("motivo") or "").strip(),
            )
        )
    return salida


@pytest.mark.parametrize(
    "indice",
    range(len(CASOS)),
    ids=[f"{numero:02d}-{caso['esperado']}" for numero, caso in enumerate(CASOS, start=1)],
)
def test_caso_individual(indice: int, resultados: list[Resultado]) -> None:
    """Reporta caso por caso; un fallo se marca como xfail, no rompe la suite."""
    resultado = resultados[indice]
    if not resultado.acertado:
        pytest.xfail(
            f"esperado={resultado.esperado}, obtenido={resultado.obtenido} "
            f"(motivo: {resultado.motivo})"
        )
    assert resultado.acertado


def test_minimo_de_aciertos(resultados: list[Resultado]) -> None:
    """El router debe acertar al menos MINIMO_ACERTADOS de los 15 casos."""
    aciertos = sum(1 for resultado in resultados if resultado.acertado)
    fallados = [resultado for resultado in resultados if not resultado.acertado]
    detalle = "\n".join(
        f'- [{r.numero}] esperado={r.esperado}, obtenido={r.obtenido}: "{r.mensaje}"'
        for r in fallados
    ) or "ninguno"

    assert aciertos >= MINIMO_ACERTADOS, (
        f"Solo {aciertos}/{len(resultados)} aciertos "
        f"(mínimo {MINIMO_ACERTADOS}).\nFallados:\n{detalle}"
    )
