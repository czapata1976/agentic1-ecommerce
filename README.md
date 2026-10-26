# Ecommerce Router — LangGraph + FastAPI + Telegram

API y agentes en **Python 3.12** para el chat de un ecommerce.

El agente `router` recibe el mensaje de un cliente, lo clasifica con salida
estructurada de Gemini y lo deriva a uno de tres destinos:

| Ruta | Cuándo se usa |
| --- | --- |
| `preventa` | Intención de compra, productos, precios, tallas, stock, promociones, formas de pago. |
| `postventa` | Quejas, reclamos, seguimiento de un pedido, devoluciones, cambios, garantía, producto dañado. |
| `generica` | Cualquier tema ajeno a la tienda (clima, chistes, preguntas generales) o saludos sin pedido. |

La decisión (`ruta` + `motivo`) y la `respuesta` quedan en el estado del grafo,
con memoria por conversación (`thread_id`) usando `MemorySaver`. Los tres nodos
destino son **cascarones**: por ahora responden un texto fijo y se completarán
más adelante.

La misma lógica se expone por HTTP con FastAPI, incluye una colección de Bruno,
está preparada para desplegarse en Heroku y deja listo el webhook de Telegram.

## Estructura

```text
.
├── main.py                 # CLI para ejecutar agentes
├── api/app.py              # FastAPI: /health, /chat, /telegram
├── src/
│   ├── config.py           # lectura de variables de entorno
│   ├── llm.py              # fábrica del modelo Gemini
│   ├── agentes.py          # carga dinámica de agentes
│   ├── asistente/          # agente de ejemplo
│   └── router/             # router del ecommerce (graph, prompts, tools)
├── scripts/                # utilidades (verificar_entorno, test_router)
├── tests/                  # pytest + casos_router.json
├── bruno/                  # colección de peticiones HTTP
├── Procfile                # arranque en Heroku
└── requirements.txt
```

## Requisitos

- Python 3.12
- Una clave de Google AI Studio (`GOOGLE_API_KEY`)
- Opcional: [Bruno](https://www.usebruno.com/), Heroku CLI y ngrok

## Variables de entorno

Copiar `.env.example` a `.env` y rellenar los valores. **El `.env` nunca se
sube al repositorio** (está en `.gitignore`).

| Variable | Obligatoria | Descripción | Ejemplo |
| --- | --- | --- | --- |
| `GOOGLE_API_KEY` | Sí | Clave de Google AI Studio. | `AQ.Ab8...` |
| `MODELO` | Sí | Modelo de Gemini. | `gemini-3.5-flash-lite` |
| `TELEGRAM_TOKEN` | Solo Telegram | Token que entrega BotFather. | `123456:ABC...` |
| `TELEGRAM_SECRET` | Solo Telegram | Secreto que Telegram envía en cada webhook. | `cambiame` en local |
| `PUBLIC_URL` | Solo Telegram | URL `https://` pública del servicio. | `https://mi-app.herokuapp.com` |

`PORT` no se define en `.env`: en Heroku lo inyecta la plataforma y `Procfile`
lo usa con `$PORT`.

## Puesta en marcha en local

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Linux / macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Verificar que todo está configurado:

```powershell
python scripts/verificar_entorno.py
```

## Correr el router en local

```powershell
# Un mensaje, mostrando la ruta elegida y el motivo
python main.py router "¿tienen la polera azul en talla M?" --saltos

# Memoria por conversación (thread_id)
python main.py router "mi pedido 4521 llegó roto" --saltos --thread cliente-1

# Imprimir el diagrama Mermaid sin ejecutar el grafo
python main.py router --diagrama

# Los quince casos de tests/casos_router.json en una tabla con ✔/✘
python scripts/test_router.py
```

Salida de ejemplo:

```text
[saltos] router -> agente_postventa
[motivo] El cliente reporta un problema con un pedido ya realizado.
Soy el agente de postventa. Recibí: mi pedido 4521 llegó roto. Pronto podré ayudarte con tu pedido.
```

## Levantar la API

```powershell
uvicorn api.app:app --reload --port 8000
```

| Ruta | Método | Descripción |
| --- | --- | --- |
| `/health` | GET | `{"ok": true, "modelo": MODELO}` |
| `/chat` | POST | Body `{"user_id", "texto"}`; usa `user_id` como `thread_id`. |
| `/telegram` | POST | Webhook de Telegram (oculto del Swagger). |

Swagger con ejemplos listos para "Try it out":
<http://localhost:8000/docs>

Probar desde la terminal (Windows PowerShell):

```powershell
curl.exe http://localhost:8000/health

# Ojo: PowerShell 5.1 borra las comillas internas que se escapan con \" al
# llamar a curl.exe, así que el body se arma con ConvertTo-Json y va en UTF-8.
$body = @{ user_id = "cliente-123"; texto = "mi pedido 4521 llegó roto" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/chat -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

En bash, Git Bash o Linux / macOS:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"cliente-123","texto":"mi pedido 4521 llegó roto"}'
```

Si los acentos se ven raros en una consola antigua de Windows, es el visor y no
la API (responde UTF-8 válido): revisa la misma llamada en `/docs` o usa `pwsh`.

Respuesta:

```json
{
  "ruta": "postventa",
  "motivo": "El cliente reporta un problema con un pedido ya realizado.",
  "respuesta": "Soy el agente de postventa. Recibí: mi pedido 4521 llegó roto. Pronto podré ayudarte con tu pedido."
}
```

También puedes abrir `bruno/` en Bruno y ejecutar `health`, `chat-preventa`,
`chat-postventa` y `chat-generica`; la URL sale de `{{baseUrl}}` y se cambia
eligiendo el entorno `Local` o `Heroku`.

## Correr las pruebas

```powershell
# Suite rápida: no llama al modelo ni consume cuota
python -m pytest -q -m "not integracion"

# Router contra el modelo real: 15 casos, exige 13 aciertos
python -m pytest -q -m integracion
```

La suite por defecto usa un LLM falso: verifica la estructura del grafo, el
contrato de la API, el OpenAPI y la CLI. Los casos marcados como `integracion`
(`tests/test_router.py`, leídos de `tests/casos_router.json`) sí llaman a Gemini,
necesitan `GOOGLE_API_KEY` y exigen **al menos 13 de 15** aciertos porque el
modelo no es determinista.

## Despliegue en Heroku

Requisitos: Heroku CLI instalada y el repositorio con commits.

```powershell
heroku login
heroku create
```

`heroku create` agrega el remoto `heroku` y muestra la URL de la app. Luego:

```powershell
heroku config:set GOOGLE_API_KEY=tu-clave-aqui MODELO=gemini-3.5-flash-lite
heroku config:set TELEGRAM_SECRET=cambiame
heroku config:set PUBLIC_URL=https://nombre-de-tu-app.herokuapp.com
git push heroku main
heroku open
```

Comprobar el despliegue:

```powershell
curl.exe https://nombre-de-tu-app.herokuapp.com/health
heroku logs --tail
```

`Procfile` (`web: uvicorn api.app:app --host 0.0.0.0 --port $PORT`) y
`.python-version` (`3.12`) ya están listos. Cada vez que agregues una
dependencia, actualiza también `requirements.txt`.

## Conectar Telegram

La API habla con Telegram por HTTPS con `httpx`, sin librerías de bot:
`POST /telegram` (oculto del Swagger) valida el secreto, responde `200` al
instante y deja el enrutamiento y el `sendMessage` en segundo plano. Así, si el
modelo tarda, Telegram ya recibió su `200` y no reintenta el update (el usuario
no recibe la respuesta dos veces).

1. **Crea el bot y guarda los secretos.** En Telegram habla con
   [@BotFather](https://t.me/BotFather), ejecuta `/newbot` y guarda el token en
   `TELEGRAM_TOKEN`. Elige un `TELEGRAM_SECRET` largo y aleatorio: Telegram lo
   manda en cada webhook en la cabecera `X-Telegram-Bot-Api-Secret-Token` y la
   API lo compara (si no coincide responde **403**). En local, copia ambos a
   `.env`.

2. **Configura Heroku.**

   ```powershell
   heroku config:set TELEGRAM_TOKEN=123456:ABC-tu-token TELEGRAM_SECRET=tu-secreto
   heroku config:set PUBLIC_URL=https://nombre-de-tu-app.herokuapp.com
   heroku config:get PUBLIC_URL
   ```

3. **Publica los cambios** en GitHub y en Heroku:

   ```powershell
   git add .
   git commit -m "telegram: webhook + scripts"
   git push origin main
   git push heroku main
   ```

4. **Registra y comprueba el webhook** desde la raíz del proyecto:

   ```powershell
   python scripts/set_webhook.py
   python scripts/webhook_info.py
   ```

   `set_webhook.py` llama a `setWebhook` con `PUBLIC_URL + "/telegram"` y el
   `secret_token`, e imprime la respuesta de Telegram. `webhook_info.py` llama a
   `getWebhookInfo` y avisa si el webhook apunta a otra URL, si hay updates
   pendientes o si quedó un último error registrado.

5. **Prueba los 6 mensajes.** Deja `heroku logs --tail` abierto en otra terminal
   y escribe al bot:

   | Mensaje | Ruta esperada |
   | --- | --- |
   | `¿tienen la polera azul en talla M?` | `preventa` |
   | `¿cuánto cuesta el envío a Valparaíso?` | `preventa` |
   | `mi pedido 4521 llegó roto` | `postventa` |
   | `quiero devolver unas zapatillas` | `postventa` |
   | `hola` | `generica` |
   | `¿qué hora es en Tokio?` | `generica` |

   Cada mensaje deja la decisión del router en el log:

   ```text
   INFO:api.router: chat_id=123456789 ruta=postventa motivo=El cliente reporta un pedido dañado.
   ```

6. **Si el bot no responde**, revisa en este orden:

   - `python scripts/webhook_info.py`: la `url` debe ser `https://.../telegram`
     (con `https` y la ruta `/telegram`) y `pending_update_count` debe estar bajo.
   - Que `TELEGRAM_SECRET` sea idéntico en Heroku y en el `setWebhook`; si no,
     la API responde 403 y Telegram lo refleja en `last_error_message`.
   - Que `TELEGRAM_TOKEN` sea el de BotFather (`getWebhookInfo` lo delata con
     `Unauthorized`).
   - `heroku logs --tail`: ahí aparecen los 403, los 500 y los errores de
     `sendMessage`, sin exponer el token.

### Probar en local antes de desplegar (opcional)

```powershell
cloudflared tunnel --url http://localhost:8000
```

Copia la URL `https://algo.trycloudflare.com` en el `PUBLIC_URL` del `.env`,
levanta la API con `uvicorn api.app:app --reload --port 8000` y corre
`python scripts/set_webhook.py`. Cuando termines, desconecta el webhook:

```powershell
curl.exe -X POST "https://api.telegram.org/bot123456:ABC-tu-token/deleteWebhook"
```

## Reglas del proyecto

Las convenciones de agentes, prompts, scripts y despliegue están en
[`AGENTS.md`](AGENTS.md).
