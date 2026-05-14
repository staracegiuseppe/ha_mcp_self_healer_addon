import logging
import json
from contextlib import asynccontextmanager
from html import escape

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from agent import SelfHealingAgent
from config import load_settings
from knowledge_base import list_known_issues
from mcp_http import handle_mcp
from playbooks import list_capabilities

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

settings = load_settings()
agent = SelfHealingAgent(settings)
APP_VERSION = "0.2.13"
APP_AUTHOR = "Starace Giuseppe"
PAYPAL_DONATE_URL = "https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR"

COMPONENTS = {
    "homeassistant_core": ("Home Assistant Core", "Core, configurazione, template, recorder e API."),
    "supervisor_host": ("Supervisor e host", "Supervisor, add-on, rete host, update e backup."),
    "mqtt_zigbee": ("MQTT e Zigbee", "Zigbee2MQTT, payload MQTT, coordinator e dispositivi unavailable."),
    "automations": ("Automazioni", "Loop, trace, automazioni bloccate o riavviate."),
    "browser_mod": ("Browser Mod", "Browser obsoleti, device fantasma e pannelli kiosk."),
    "voice_assistants": ("Alexa / Emulated Hue", "Entita' esposte, discovery vocale e client Hue-compatible."),
    "media_cast": ("Media / Cast", "Chromecast, TV, pychromecast e socket media."),
    "cameras": ("Camera e stream", "Telecamere, stream, ffmpeg e snapshot."),
    "network_devices": ("Dispositivi LAN", "REST sensor, Sonoff, Govee, Fully Kiosk e device HTTP."),
    "updates": ("Aggiornamenti", "Entita' update, versioni e richieste di installazione."),
    "self_healer": ("Self Healer", "Salute interna dell'add-on e dei playbook."),
    "other": ("Altro", "Errori non ancora classificati."),
}

COMPONENT_RULES = [
    ("self_healer", ("ha_mcp_self_healer", "self healer", "self-healer")),
    ("browser_mod", ("browser_mod", "browser mod")),
    ("voice_assistants", ("emulated_hue", "hue_api", "alexa", "google assistant")),
    ("mqtt_zigbee", ("zigbee", "zha", "z2m", "mqtt", "bridge_update", "permit_join", "coordinator")),
    ("automations", ("automation.", "automazione", "loop automazione", "script.")),
    ("media_cast", ("pychromecast", "cast", "chromecast", "connection reset by peer")),
    ("cameras", ("camera", "stream", "ffmpeg", "snapshot", "ezviz")),
    ("network_devices", ("rest.data", "fully", "sonoff", "govee", "connect call failed", "device stopped responding")),
    ("updates", ("update.", "no update available", "installing a specific version", "appmanager.update")),
    ("supervisor_host", ("supervisor", "host internet", "hassio", "backup", "addon")),
    ("homeassistant_core", ("homeassistant.helpers.template", "invalidstateerror", "configentry", "recorder", "yaml")),
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    agent.start_background()
    try:
        yield
    finally:
        agent.stop()


app = FastAPI(title="Home Assistant MCP Self Healer", version=APP_VERSION, lifespan=lifespan)


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
          .meta {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 10px; }}
          .panel {{ background: white; border: 1px solid #d9dee7; border-radius: 8px; padding: 18px; margin-top: 16px; }}
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
          .metric {{ background: #ffffff; border: 1px solid #d9dee7; border-radius: 8px; padding: 14px; }}
          .label {{ color: #687386; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
          .value {{ font-size: 20px; font-weight: 700; margin-top: 4px; word-break: break-word; }}
          .badge {{ display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; }}
          .ok {{ background: #dff7e8; color: #126b35; }}
          .warn {{ background: #fff1cf; color: #7a4d00; }}
          .err {{ background: #ffe1df; color: #9b231e; }}
          .neutral {{ background: #e8edf5; color: #334155; }}
          .health-card {{ border-left: 5px solid #cbd5e1; }}
          .health-card.health-ok {{ border-left-color: #23a455; }}
          .health-card.health-warn {{ border-left-color: #d28a00; }}
          .health-card.health-err {{ border-left-color: #d33b32; }}
          .health-card.health-neutral {{ border-left-color: #94a3b8; }}
          .muted {{ color: #687386; }}
          code, pre {{ background: #eef1f6; border-radius: 6px; }}
          code {{ padding: 2px 5px; }}
          pre {{ padding: 14px; overflow: auto; white-space: pre-wrap; }}
          a.button {{ display: inline-block; background: #1f6feb; color: white; padding: 10px 14px; border-radius: 6px; text-decoration: none; margin-right: 8px; margin-top: 6px; }}
          a.secondary {{ background: #4b5563; }}
          a.donate {{ background: #0070ba; }}
          footer {{ color: #687386; font-size: 13px; padding: 18px 0 4px; }}
          ul {{ padding-left: 20px; }}
          li {{ margin: 8px 0; }}
        </style>
      </head>
      <body>
        <main>
          {body}
          <footer>
            <span>Autore: {escape(APP_AUTHOR)}</span>
            <span> · </span>
            <a href="{escape(PAYPAL_DONATE_URL)}" target="_blank" rel="noopener">Donate PayPal: staracegiuseppe@gmail.com</a>
          </footer>
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
      <div class="metric"><div class="label">Loop monitor</div><div class="value">{escape(str(status.get("loop_monitor_enabled")))}</div></div>
      <div class="metric"><div class="label">Finestra loop</div><div class="value">{escape(str(status.get("loop_window_minutes")))} min</div></div>
      <div class="metric"><div class="label">Stop automazioni</div><div class="value">{escape(str(status.get("allow_automation_disable")))}</div></div>
      <div class="metric"><div class="label">TTL errori visti</div><div class="value">{escape(str(status.get("seen_ttl_hours")))} h</div></div>
      <div class="metric"><div class="label">Errori gia' visti</div><div class="value">{escape(str(status.get("seen_errors")))}</div></div>
      <div class="metric"><div class="label">Report salvati</div><div class="value">{escape(str(status.get("history_count")))}</div></div>
      <div class="metric"><div class="label">HA URL</div><div class="value" style="font-size:14px">{escape(str(status.get("ha_url", "")))}</div></div>
      <div class="metric"><div class="label">Supervisor URL</div><div class="value" style="font-size:14px">{escape(str(status.get("supervisor_url", "")))}</div></div>
    </div>
    """


def _component_from_text(text: str) -> str:
    lowered = text.lower()
    for key, needles in COMPONENT_RULES:
        if any(needle in lowered for needle in needles):
            return key
    return "other"


def _clip(value: object, limit: int = 180) -> str:
    text = str(value or "")
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _empty_component(key: str) -> dict:
    title, description = COMPONENTS.get(key, COMPONENTS["other"])
    return {
        "key": key,
        "title": title,
        "description": description,
        "status": "ok",
        "issues": 0,
        "actions": 0,
        "severity_counts": {"critical": 0, "error": 0, "warning": 0, "info": 0},
        "action_counts": {"success": 0, "failed": 0, "dry_run": 0, "skipped": 0},
        "latest_issue": None,
        "latest_action": None,
    }


def _health_snapshot() -> dict:
    status = agent.status()
    reports = agent.history()
    last_report = status.get("last_report")
    if last_report:
        reports = [last_report] + [report for report in reports if report != last_report]

    components = {key: _empty_component(key) for key in COMPONENTS}
    timeline = []
    totals = {"issues": 0, "actions": 0, "success": 0, "failed": 0, "dry_run": 0, "skipped": 0}

    for report in reports[:50]:
        stamp = str(report.get("finished_at") or report.get("started_at") or "")
        for issue in report.get("issues") or []:
            text = " ".join(str(issue.get(field, "")) for field in ("source", "message", "traceback"))
            key = _component_from_text(text)
            component = components.setdefault(key, _empty_component(key))
            severity = str(issue.get("severity") or "info").lower()
            if severity not in component["severity_counts"]:
                severity = "info"
            component["issues"] += 1
            component["severity_counts"][severity] += 1
            component["latest_issue"] = component["latest_issue"] or {
                "time": stamp,
                "severity": severity,
                "source": issue.get("source"),
                "message": issue.get("message"),
            }
            totals["issues"] += 1
            if len(timeline) < 12:
                timeline.append({
                    "time": stamp,
                    "component": component["title"],
                    "kind": "issue",
                    "status": severity,
                    "text": _clip(issue.get("message"), 220),
                })

        for result in report.get("actions") or []:
            action = result.get("action") or {}
            text = " ".join(str(action.get(field, "")) for field in ("kind", "title", "reason", "payload"))
            key = _component_from_text(text)
            component = components.setdefault(key, _empty_component(key))
            action_status = str(result.get("status") or "skipped").lower()
            if action_status not in component["action_counts"]:
                action_status = "skipped"
            component["actions"] += 1
            component["action_counts"][action_status] += 1
            component["latest_action"] = component["latest_action"] or {
                "time": stamp,
                "status": action_status,
                "title": action.get("title"),
                "detail": result.get("detail") or action.get("reason"),
            }
            totals["actions"] += 1
            totals[action_status] = totals.get(action_status, 0) + 1
            if len(timeline) < 12:
                timeline.append({
                    "time": stamp,
                    "component": component["title"],
                    "kind": "action",
                    "status": action_status,
                    "text": _clip(action.get("title") or result.get("detail"), 220),
                })

    for component in components.values():
        if component["action_counts"]["failed"] or component["severity_counts"]["critical"] or component["severity_counts"]["error"]:
            component["status"] = "err"
        elif component["issues"] or component["action_counts"]["dry_run"] or component["action_counts"]["skipped"]:
            component["status"] = "warn"
        else:
            component["status"] = "ok"

    issue_components = [component for component in components.values() if component["issues"] or component["actions"]]
    if totals["failed"] or any(component["status"] == "err" for component in components.values()):
        overall_status = "err"
        overall_label = "Attenzione"
    elif totals["issues"] or totals["dry_run"] or totals["skipped"]:
        overall_status = "warn"
        overall_label = "Da osservare"
    else:
        overall_status = "ok"
        overall_label = "Stabile"

    enabled_fixes = [
        {"title": "Auto-fix", "enabled": bool(status.get("auto_fix_enabled"))},
        {"title": "Dry run", "enabled": bool(status.get("dry_run")), "inverse": True},
        {"title": "Loop automazioni", "enabled": bool(status.get("loop_monitor_enabled"))},
        {"title": "Riavvio automazioni", "enabled": bool(status.get("allow_automation_restart"))},
        {"title": "Stop automazioni", "enabled": bool(status.get("allow_automation_disable"))},
        {"title": "Browser Mod cleanup", "enabled": bool(status.get("allow_browser_mod_cleanup"))},
        {"title": "Alexa exposure reload", "enabled": bool(status.get("allow_alexa_exposure_reload"))},
        {"title": "MQTT state patch", "enabled": bool(status.get("allow_mqtt_state_patch"))},
        {"title": "Update install", "enabled": bool(status.get("allow_update_install"))},
    ]

    return {
        "overall": {"status": overall_status, "label": overall_label},
        "totals": totals,
        "agent": status,
        "components": list(components.values()),
        "active_components": issue_components,
        "enabled_fixes": enabled_fixes,
        "timeline": timeline,
    }


def _health_dashboard_html(snapshot: dict) -> str:
    overall = snapshot["overall"]
    totals = snapshot["totals"]
    components = snapshot["components"]
    enabled_fixes = snapshot["enabled_fixes"]
    timeline = snapshot["timeline"]

    summary_cards = f"""
    <div class="grid">
      <div class="metric health-card health-{escape(overall['status'])}"><div class="label">Salute generale</div><div class="value"><span class="badge {escape(overall['status'])}">{escape(overall['label'])}</span></div></div>
      <div class="metric"><div class="label">Errori nello storico</div><div class="value">{escape(str(totals.get("issues", 0)))}</div></div>
      <div class="metric"><div class="label">Fix riusciti</div><div class="value">{escape(str(totals.get("success", 0)))}</div></div>
      <div class="metric"><div class="label">Fix falliti</div><div class="value">{escape(str(totals.get("failed", 0)))}</div></div>
      <div class="metric"><div class="label">Azioni simulate/saltate</div><div class="value">{escape(str(totals.get("dry_run", 0) + totals.get("skipped", 0)))}</div></div>
    </div>
    """

    fix_cards = "".join(
        f"<div class='metric'><div class='label'>{escape(item['title'])}</div><div class='value'><span class='badge {'warn' if item.get('inverse') and item.get('enabled') else 'ok' if item.get('enabled') else 'neutral'}'>{escape('ON' if item.get('enabled') else 'OFF')}</span></div></div>"
        for item in enabled_fixes
    )

    component_cards = "".join(
        f"""
        <div class="metric health-card health-{escape(component['status'])}">
          <div class="label">{escape(component['description'])}</div>
          <h2>{escape(component['title'])}</h2>
          <p><span class="badge {escape(component['status'])}">{escape('OK' if component['status'] == 'ok' else 'ATTENZIONE' if component['status'] == 'warn' else 'ERRORE')}</span></p>
          <p>Errori: <b>{escape(str(component['issues']))}</b> · Azioni: <b>{escape(str(component['actions']))}</b></p>
          <p class="muted">{escape(_clip((component.get('latest_issue') or component.get('latest_action') or {}).get('message') or (component.get('latest_action') or {}).get('title') or 'Nessun evento recente.'))}</p>
        </div>
        """
        for component in components
    )

    timeline_items = "".join(
        f"<li><span class='badge {'ok' if item.get('status') == 'success' else 'err' if item.get('status') in ('error', 'critical', 'failed') else 'warn'}'>{escape(str(item.get('kind', '')).upper())}</span> <b>{escape(str(item.get('component', '')))}</b><br><span>{escape(str(item.get('text') or ''))}</span><br><span class='muted'>{escape(str(item.get('time') or ''))}</span></li>"
        for item in timeline
    ) or "<li class='muted'>Nessun evento ancora registrato.</li>"

    return f"""
    <section class="panel">
      <h2>Quadro generale</h2>
      {summary_cards}
    </section>
    <section class="panel">
      <h2>Fix automatici abilitati</h2>
      <div class="grid">{fix_cards}</div>
    </section>
    <section class="panel">
      <h2>Salute componenti</h2>
      <div class="grid">{component_cards}</div>
    </section>
    <section class="panel">
      <h2>Ultimi eventi</h2>
      <ul>{timeline_items}</ul>
    </section>
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


def _capabilities_html() -> str:
    cards = []
    for capability in list_capabilities():
        triggers = "".join(f"<li><code>{escape(str(trigger))}</code></li>" for trigger in capability.get("triggers", []))
        cards.append(f"""
        <section class="panel">
          <h2>{escape(str(capability.get("title", "")))}</h2>
          <p><span class="badge ok">{escape(str(capability.get("kind", "")))}</span></p>
          <div class="grid">
            <div class="metric"><div class="label">Cosa rileva</div><ul>{triggers}</ul></div>
            <div class="metric"><div class="label">Cosa fa</div><p>{escape(str(capability.get("action", "")))}</p></div>
            <div class="metric"><div class="label">Sicurezza</div><p>{escape(str(capability.get("safety", "")))}</p></div>
            <div class="metric"><div class="label">Come migliorarlo</div><p>{escape(str(capability.get("improvement_hint", "")))}</p></div>
          </div>
        </section>
        """)
    return "".join(cards)


def _known_issues_html() -> str:
    grouped: dict[str, list[dict]] = {}
    for issue in list_known_issues():
        grouped.setdefault(str(issue.get("category", "Altro")), []).append(issue)

    sections = []
    for category, issues in grouped.items():
        cards = "".join(
            f"""
            <div class="metric">
              <div class="label">{escape(str(issue.get("automation_level", "")))}</div>
              <h2>{escape(str(issue.get("title", "")))}</h2>
              <p>{escape(str(issue.get("diagnosis", "")))}</p>
              <p class="muted">{escape(str(issue.get("safe_response", "")))}</p>
            </div>
            """
            for issue in issues
        )
        sections.append(f"""
        <section class="panel">
          <h2>{escape(category)}</h2>
          <div class="grid">{cards}</div>
        </section>
        """)
    return "".join(sections)


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
          <div class="meta">
            <span class="badge ok">Autore: {escape(APP_AUTHOR)}</span>
            <span class="badge warn">Versione {escape(APP_VERSION)}</span>
            <a class="button donate" href="{escape(PAYPAL_DONATE_URL)}" target="_blank" rel="noopener">Donate PayPal</a>
          </div>
        </div>
      </div>
      {_status_metrics(status)}
      <p><a class="button" href="run-once">Esegui controllo ora</a><a class="button secondary" href="dashboard">Plancia salute</a><a class="button secondary" href="health">Stato agente</a><a class="button secondary" href="history">Storico</a><a class="button secondary" href="capabilities">Capacita'</a><a class="button donate" href="support">Supporto</a></p>
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


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> str:
    snapshot = _health_snapshot()
    return _page("Plancia salute componenti", f"""
      <h1>Plancia salute componenti</h1>
      <p class="muted">Vista aggregata dello stato dell'add-on, dei componenti Home Assistant osservati, dei fix automatici e degli ultimi eventi.</p>
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button" href="run-once">Esegui controllo ora</a><a class="button secondary" href="dashboard.json">JSON salute</a><a class="button secondary" href="history">Storico</a></p>
      {_health_dashboard_html(snapshot)}
    """)


@app.get("/dashboard.json")
def dashboard_json() -> dict:
    return _health_snapshot()


@app.get("//dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard_page_double_slash() -> str:
    return dashboard_page()


@app.get("//dashboard.json", include_in_schema=False)
def dashboard_json_double_slash() -> dict:
    return dashboard_json()


@app.get("/health", response_class=HTMLResponse)
def health_page() -> str:
    status = agent.status()
    raw = {"ok": True, "agent": status}
    return _page("Stato agente", f"""
      <h1>Stato agente</h1>
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button" href="run-once">Esegui controllo ora</a><a class="button secondary" href="dashboard">Plancia salute</a><a class="button secondary" href="history">Storico</a><a class="button secondary" href="capabilities">Capacita'</a></p>
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


@app.get("/support", response_class=HTMLResponse)
def support_page() -> str:
    return _page("Supporto HA MCP Self Healer", f"""
      <h1>Supporto e sviluppo</h1>
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button donate" href="{escape(PAYPAL_DONATE_URL)}" target="_blank" rel="noopener">Donate PayPal</a></p>
      <section class="panel">
        <h2>Autore</h2>
        <p><b>{escape(APP_AUTHOR)}</b></p>
        <p>Email: <a href="mailto:staracegiuseppe@gmail.com">staracegiuseppe@gmail.com</a></p>
      </section>
      <section class="panel">
        <h2>Supporto professionale</h2>
        <div class="grid">
          <div class="metric"><div class="label">Quick fix review</div><div class="value">EUR 49</div><p>Revisione log e indicazione fix.</p></div>
          <div class="metric"><div class="label">Sessione remota</div><div class="value">EUR 149</div><p>Diagnosi Home Assistant e configurazione self-healer.</p></div>
          <div class="metric"><div class="label">Playbook custom</div><div class="value">da EUR 299</div><p>Nuove remediation per errori ricorrenti.</p></div>
          <div class="metric"><div class="label">Piano managed</div><div class="value">da EUR 29/mese</div><p>Supporto reliability per impianti complessi.</p></div>
        </div>
      </section>
      <section class="panel">
        <h2>Per installatori</h2>
        <p>HA MCP Self Healer puo' diventare un servizio di manutenzione per case, B&B, uffici e dashboard always-on.</p>
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


@app.get("/capabilities", response_class=HTMLResponse)
def capabilities_page() -> str:
    return _page("Capacita' autonome", f"""
      <h1>Capacita' autonome</h1>
      <p class="muted">Queste sono le remediation che l'app puo' decidere in autonomia in base ai log. Le azioni invasive restano bloccate dalle opzioni di sicurezza e dal dry-run.</p>
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button" href="run-once">Esegui controllo ora</a><a class="button secondary" href="dashboard">Plancia salute</a><a class="button secondary" href="history">Storico</a></p>
      {_capabilities_html()}
      <section class="panel">
        <h2>Knowledge base diagnostica</h2>
        <p class="muted">Queste categorie migliorano diagnosi e report. Alcune sono solo informative perche' richiedono una scelta manuale o interventi fisici.</p>
      </section>
      {_known_issues_html()}
    """)


@app.get("/capabilities.json")
def capabilities_json() -> dict:
    return {"capabilities": list_capabilities(), "known_issues": list_known_issues()}


@app.get("//capabilities", response_class=HTMLResponse, include_in_schema=False)
def capabilities_page_double_slash() -> str:
    return capabilities_page()


@app.get("//capabilities.json", include_in_schema=False)
def capabilities_json_double_slash() -> dict:
    return capabilities_json()


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
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button" href="run-once">Esegui controllo ora</a><a class="button secondary" href="dashboard">Plancia salute</a><a class="button secondary" href="capabilities">Capacita'</a></p>
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
      <p><a class="button secondary" href="./">Torna alla dashboard</a><a class="button" href="dashboard">Plancia salute</a><a class="button secondary" href="health">Stato agente</a><a class="button secondary" href="history">Storico</a><a class="button secondary" href="capabilities">Capacita'</a></p>
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
