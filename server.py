import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from agent import SelfHealingAgent
from config import load_settings
from mcp_http import handle_mcp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

settings = load_settings()
agent = SelfHealingAgent(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    agent.start_background()
    try:
        yield
    finally:
        agent.stop()


app = FastAPI(title="Home Assistant MCP Self Healer", version="0.1.4", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    status = agent.status()
    last = status.get("last_report") or {}
    summary = last.get("summary") or "Nessun ciclo completato."
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>HA MCP Self Healer</title>
        <style>
          body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background: #f6f7f9; color: #172033; }}
          main {{ max-width: 920px; margin: 0 auto; padding: 32px 18px; }}
          h1 {{ font-size: 28px; margin: 0 0 8px; }}
          .panel {{ background: white; border: 1px solid #d9dee7; border-radius: 8px; padding: 18px; margin-top: 18px; }}
          code {{ background: #eef1f6; padding: 2px 5px; border-radius: 4px; }}
          a.button {{ display: inline-block; background: #1f6feb; color: white; padding: 10px 14px; border-radius: 6px; text-decoration: none; margin-right: 8px; }}
        </style>
      </head>
      <body>
        <main>
          <h1>HA MCP Self Healer</h1>
          <p>Agente attivo: <b>{status["running"]}</b> · Dry-run: <b>{status["dry_run"]}</b> · Errori memorizzati: <b>{status["seen_errors"]}</b></p>
          <p><a class="button" href="/run-once">Esegui controllo ora</a><a class="button" href="/health">Health JSON</a></p>
          <section class="panel">
            <h2>Ultimo report</h2>
            <p>{summary}</p>
          </section>
          <section class="panel">
            <h2>MCP</h2>
            <p>Endpoint JSON-RPC: <code>POST /mcp</code></p>
            <p>Tool disponibili: <code>ha_self_healer_status</code>, <code>ha_check_logs</code>, <code>ha_run_self_healing</code>.</p>
          </section>
        </main>
      </body>
    </html>
    """


@app.get("//", response_class=HTMLResponse, include_in_schema=False)
def index_double_slash() -> str:
    return index()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "agent": agent.status()}


@app.get("/run-once")
def run_once_get() -> dict:
    return agent.run_once(notify=True).model_dump(mode="json")


@app.post("/run-once")
def run_once_post() -> dict:
    return agent.run_once(notify=True).model_dump(mode="json")


@app.post("/mcp")
def mcp(request: dict) -> dict:
    return handle_mcp(agent, request)


def run() -> None:
    log.info("Starting HA MCP Self Healer on %s:%s", settings.bind_host, settings.port)
    uvicorn.run(app, host=settings.bind_host, port=settings.port)


if __name__ == "__main__":
    run()
