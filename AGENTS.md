# AGENTS.md — reglas del proyecto

Reglas que debe cumplir cualquier agente o persona que trabaje en este repositorio.

## 1. Estructura de los agentes

- Cada agente vive en `src/{nombre_agente}/` y contiene **siempre** tres archivos:
  - `graph.py` — construye el grafo (nodos, aristas, estado) y expone `grafo`.
  - `prompts.py` — diccionario `PROMPTS` con **un prompt por nodo**.
  - `tools.py` — herramientas del agente en una lista `HERRAMIENTAS`.
- Cada nodo usa **su propio prompt** definido en `prompts.py`.
- **Nada de reglas dentro de `graph.py`**: ni instrucciones de comportamiento, ni texto de sistema escrito a mano. Todo el texto va en `prompts.py`.

## 2. Ejecución de agentes

Desde la raíz del proyecto:

```bash
python main.py {nombre_agente} "mensaje"
```

Banderas:

- `--saltos`: imprime los nodos por los que pasó el grafo.
- `--diagrama`: imprime el Mermaid del grafo **sin ejecutarlo**.

Ejemplos:

```bash
python main.py asistente "¿Qué hora es?"
python main.py asistente "¿Qué hora es?" --saltos
python main.py asistente --diagrama
```

## 3. API

- La API está en `api/app.py` (FastAPI).
- Se levanta con:

```bash
uvicorn api.app:app --reload --port 8000
```

## 4. Scripts y pruebas

- Los scripts sueltos van en `scripts/`.
- Las pruebas van en `tests/` y se ejecutan con `pytest`.

## 5. Despliegue en Heroku

- `Procfile` con:

```text
web: uvicorn api.app:app --host 0.0.0.0 --port $PORT
```

- `.python-version` con `3.12`.
- `requirements.txt` **siempre actualizado**: si agregas una dependencia, agrégala también al archivo.

## 6. Secretos y control de versiones

- Los valores sensibles solo viven en `.env` (nunca en el código). La plantilla es `.env.example`.
- `.gitignore` debe incluir `.env`, `.venv`, `__pycache__` y `.langgraph_api`.
