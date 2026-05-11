import logging
import json
from contextlib import asynccontextmanager
from html import escape

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


app = FastAPI(title="Home Assistant MCP Self Healer", version="0.1.8", lifespan=lifespan)


def _page(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{escape(title)}</title>
        <style>
          :root {{ color-scheme: light; }}
          body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background: #f6f7f9; color: #172033; }}
          main {{ max-width: 980px; margin: 0 auto; padding: 32px 18px; }}
          h1 {{ font-size: 28px; margin: 0 0 8px; }}
          h2 {{ font-size: 18px; margin: 0 0 12px; }}
          p {{ line-height: 1.5; }}
          .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 18px; }}
          .panel {{ background: white; border: 1px solid #d9dee7; border-radius: 8px; padding: 18px; margin-top: 16px; }}
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
          .metric {{ background: #ffffff; border: 1px solid #d9dee7; border-radius: 8px; padding: 14px; }}
          .label {{ color: #687386; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
          .value {{ font-size: 20px; font-weight: 700; margin-top: 4px; word-break: break-word; }}
          .badge {{ display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; }}
          .ok {{ background: #dff7e8; color: #126b35; }}
          .warn {{ background: #fff1cf; color: #7a4d00; }}
          .err {{ background: #ffe1df; color: #9b231e; }}
          .muted {{ color: #687386; }}
          code, pre {{ background: #eef1f6; border-radius: 6px; }}
          code {{ padding: 2px 5px; }}
          pre {{ padding: 14px; overflow: auto; white-space: pre-wrap; }}
          a.button {{ display: inline-block; background: #1f6feb; color: white; padding: 10px 14px; border-radius: 6px; text-decoration: none; margin-right: 8px; margin-top: 6px; }}
          a.secondary {{ background: #4b5563; }}
          ul {{ padding-left: 20px; }}
          li {{ margin: 8px 0; }}
        </style>
      </head>
      <body>
        <main>
          {body}
        </main>
      </body>
    </html>
    """


def _status_metrics(status: dict) -> str:
    running_class = "ok" if status.get("running") else "err"
    dry_run_class = "warn" if status.get("dry_run") else "ok"
    return f"""
    <div class="grid">
      <div class="metric"><div class="label">Agente</div><div class="value"><span class="badge {running_class}">{escape(str(status.get("running")))}</span></div></div>
      <div class="metric"><div class="label">Dry run</div><div class="value"><span class="badge {dry_run_class}">{escape(str(status.get("dry_run")))}</span></div></div>
      <div class="metric"><div class="label">Auto-fix</div><div class="value">{escape(str(status.get("auto_fix_enabled")))}</div></div>
      <div class="metric"><div class="label">Errori gia' visti</div><div class="value">{escape(str(status.get("seen_errors")))}</div></div>
      <div class="metric"><div class="label">Report salvati</div><div class="value">{escape(str(status.get("history_count")))}</div></div>
      <div class="metric"><div class="label">HA URL</div><div class="value" style="font-size:14px">{escape(str(status.get("ha_url", "")))}</div></div>
      <div class="metric"><div class="label">Supervisor URL</div><div class="value" style="font-size:14px">{escape(str(status.get("supervisor_url", "")))}</div></div>
    </div>
    """


def _report_html(report: dict) -> str:
    issues = report.get("issues") or []
    actions = report.get("actions") or []
    issues_html = "".join(
        f"<li><span class='badge {'err' if item.get('severity') in ('error', 'critical') else 'warn'}'>{escape(str(item.get('severity', 'unknown')).upper())}</span> "
        f"<b>{escape(str(item.get('source', 'unknown')))}</b><br><span>{escape(str(item.get('message', '')))}</span></li>"
        for item in issues
    ) or "<li class='muted'>Nessun nuovo errore rilevato.</li>"
    actions_html = "".join(
        f"<li><span class='badge {'ok' if item.get('status') == 'success' else 'warn' if item.get('status') in ('dry_run', 'skipped') else 'err'}'>{escape(str(item.get('status', 'unknown')).upper())}</span> "
        f"<b>{escape(str((item.get('action') or {}).get('title', 'Azione')))}</b><br><span>{escape(str(item.get('detail') or (item.get('action') or {}).get('reason', '')))}</span></li>"
        for item in actions
    ) or "<li class='muted'>Nessuna azione eseguita.</li>"
    return f"""
    <section class="panel">
      <h2>Riepilogo</h2>
      <p>{escape(str(report.get("summary") or "Nessun riepilogo disponibile."))}</p>
    </section>
    <section class="panel">
      <h2>Errori rilevati</h2>
      <ul>{issues_html}</ul>
    </section>
    <section class="panel">
      <h2>Azioni</h2>
      <ul>{actions_html}</ul>
    </section>
    <section class="panel">
      <h2>Dettaglio tecnico</h2>
      <pre>{escape(json.dumps(report, ensure_ascii=False, indent=2))}</pre>
    </section>
    """


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    status = agent.status()
    last = status.get("last_report") or {}
    summary = last.get("summary") or "Nessun ciclo completato."
    return _page("HA MCP Self Healer", f"""
      <div class="topbar">
        <div>
          <h1>HA MCP Self Healer</h1>
          <p class="muted">Monitoraggio log, remediation conservativa e report email.</p>
        </div>
      </div>
      {_status_metrics(status)}
      <p><a class="button" href="run-once">Esegui controllo ora</a><a class="button secondary" href="health">Stato agente</a><a class="button secondary" href="history">Storico</a></p>
      <section class="panel">
        <h2>Ultimo report</h2>
        <p>{escape(str(summary))}</p>
      </section>
      <section class="panel">
        <h2>MCP</h2>
        <p>Endpoint JSON-RPC: <code>POST /mcp</code></p>
        <p class="muted">Tool disponibili: <code>ha_self_healer_status</code>, <code>ha_check_logs</code>, <code>ha_run_self_healing</code>.</p>
      </section>
    """)


@app.get("//", response_class=HTMLResponse, include_in_schema=False)
def index_double_slash() -> str:
    return index()


@app.get("/health", response_class=HTMLResponse)
def health_page() -> str:
    status = agent.status()
    raw = {"ok": True, "agent": status}
    return _page("Stato agente", f"""
      <h1>Stato agente</h1>
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button" href="run-once">Esegui controllo ora</a><a class="button secondary" href="history">Storico</a></p>
      {_status_metrics(status)}
      <section class="panel">
        <h2>Ultimo report</h2>
        {_report_html(status.get("last_report") or {"summary": "Nessun ciclo completato.", "issues": [], "actions": []})}
      </section>
      <section class="panel">
        <h2>JSON tecnico</h2>
        <pre>{escape(json.dumps(raw, ensure_ascii=False, indent=2))}</pre>
      </section>
    """)


@app.get("/health.json")
def health() -> dict:
    return {"ok": True, "agent": agent.status()}


@app.get("//health", response_class=HTMLResponse, include_in_schema=False)
def health_double_slash() -> str:
    return health_page()


@app.get("//health.json", include_in_schema=False)
def health_json_double_slash() -> dict:
    return health()


@app.get("/history", response_class=HTMLResponse)
def history_page() -> str:
    reports = agent.history()
    if not reports:
        content = "<section class='panel'><h2>Nessuno storico</h2><p class='muted'>Non ci sono ancora errori o azioni salvate.</p></section>"
    else:
        content = "".join(
            f"<section class='panel'><h2>Report {escape(str(report.get('finished_at') or report.get('started_at') or ''))}</h2>{_report_html(report)}</section>"
            for report in reports
        )
    return _page("Storico interventi", f"""
      <h1>Storico interventi</h1>
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button" href="run-once">Esegui controllo ora</a></p>
      {content}
    """)


@app.get("/history.json")
def history_json() -> dict:
    return {"history": agent.history()}


@app.get("//history", response_class=HTMLResponse, include_in_schema=False)
def history_page_double_slash() -> str:
    return history_page()


@app.get("//history.json", include_in_schema=False)
def history_json_double_slash() -> dict:
    return history_json()


@app.get("/run-once", response_class=HTMLResponse)
def run_once_get() -> str:
    report = agent.run_once(notify=True).model_dump(mode="json")
    return _page("Controllo completato", f"""
      <h1>Controllo completato</h1>
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button" href="health">Stato agente</a><a class="button secondary" href="history">Storico</a></p>
      {_report_html(report)}
    """)


@app.get("/run-once.json")
def run_once_get_json() -> dict:
    return agent.run_once(notify=True).model_dump(mode="json")


@app.get("//run-once", response_class=HTMLResponse, include_in_schema=False)
def run_once_get_double_slash() -> str:
    return run_once_get()


@app.get("//run-once.json", include_in_schema=False)
def run_once_get_json_double_slash() -> dict:
    return run_once_get_json()


@app.post("/run-once")
def run_once_post() -> dict:
    return agent.run_once(notify=True).model_dump(mode="json")


@app.post("//run-once", include_in_schema=False)
def run_once_post_double_slash() -> dict:
    return run_once_post()


@app.post("/mcp")
def mcp(request: dict) -> dict:
    return handle_mcp(agent, request)


@app.post("//mcp", include_in_schema=False)
def mcp_double_slash(request: dict) -> dict:
    return mcp(request)


def run() -> None:
    log.info("Starting HA MCP Self Healer on %s:%s", settings.bind_host, settings.port)
    uvicorn.run(app, host=settings.bind_host, port=settings.port)


if __name__ == "__main__":
    run()
