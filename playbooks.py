import re

from config import Settings
from knowledge_base import match_known_issue
from models import HealingAction, LogIssue


CAPABILITIES = [
    {
        "kind": "reload_integration",
        "title": "Reload integrazione Home Assistant",
        "triggers": ["config entry failed", "config entry setup", "error setting up config entry", "entry_id=..."],
        "action": "Chiama homeassistant.reload_config_entry sul config entry rilevato.",
        "safety": "Consentito solo se allow_integration_reload=true. In dry-run viene solo simulato.",
        "improvement_hint": "Migliorare l'estrazione di entry_id dai log delle integrazioni piu' frequenti.",
    },
    {
        "kind": "wait_and_recheck",
        "title": "Attesa e ricontrollo",
        "triggers": ["platform not ready", "will retry"],
        "action": "Attende un breve intervallo e lascia che Home Assistant completi il retry automatico.",
        "safety": "Sempre consentito: non modifica configurazione o stato dei dispositivi.",
        "improvement_hint": "Aggiungere un secondo controllo che verifichi se l'errore e' sparito davvero.",
    },
    {
        "kind": "reload_core_config",
        "title": "Reload configurazione core",
        "triggers": ["invalid config", "configuration.yaml"],
        "action": "Chiama homeassistant.reload_core_config.",
        "safety": "Consentito solo se allow_integration_reload=true. In dry-run viene solo simulato.",
        "improvement_hint": "Aggiungere parsing del file/linea per suggerire una correzione YAML manuale.",
    },
    {
        "kind": "restart_homeassistant",
        "title": "Restart Home Assistant",
        "triggers": ["database is locked", "recorder error"],
        "action": "Crea un backup parziale se configurato e poi chiama homeassistant.restart.",
        "safety": "Disabilitato di default: richiede allow_homeassistant_restart=true.",
        "improvement_hint": "Preferire remediation recorder piu' mirate prima del restart completo.",
    },
    {
        "kind": "restart_addon",
        "title": "Restart add-on",
        "triggers": ["addon crashed", "addon exit code"],
        "action": "Chiama hassio.addon_restart sullo slug rilevato.",
        "safety": "Consentito solo se allow_addon_restart=true. In dry-run viene solo simulato.",
        "improvement_hint": "Rendere piu' robusta l'estrazione dello slug add-on dai log Supervisor.",
    },
    {
        "kind": "disable_automation",
        "title": "Stop loop automazione/luci",
        "triggers": ["automazione ripetuta molte volte nel logbook", "luce/switch/fan che alterna on/off troppe volte"],
        "action": "Chiama automation.turn_off con stop_actions=true sull'automazione sospetta.",
        "safety": "Disabilitato di default: richiede allow_automation_disable=true. In dry-run viene solo simulato.",
        "improvement_hint": "Collegare meglio dispositivo oscillante e automazione responsabile usando context_id e trace.",
    },
    {
        "kind": "notify_only",
        "title": "Solo notifica",
        "triggers": ["errore non riconosciuto"],
        "action": "Non modifica nulla: salva il report e invia email se configurata.",
        "safety": "Sempre sicuro. E' il fallback quando non esiste un playbook affidabile.",
        "improvement_hint": "Usare lo storico per creare nuovi playbook mirati agli errori ricorrenti.",
    },
]


def list_capabilities() -> list[dict]:
    return list(CAPABILITIES)


def decide_actions(issue: LogIssue, settings: Settings) -> list[HealingAction]:
    text = f"{issue.source}\n{issue.message}\n{issue.traceback}".lower()
    actions: list[HealingAction] = []

    if "config entry" in text and ("failed" in text or "setup" in text or "setting up" in text):
        entry_id = _extract_entry_id(text)
        if entry_id:
            actions.append(HealingAction(
                kind="reload_integration",
                title="Reload integrazione Home Assistant",
                reason="Il log indica un config entry in errore o non inizializzato.",
                allowed=settings.allow_integration_reload,
                payload={"entry_id": entry_id},
            ))

    if "platform not ready" in text or "will retry" in text:
        actions.append(HealingAction(
            kind="wait_and_recheck",
            title="Attesa e ricontrollo",
            reason="Home Assistant segnala un errore temporaneo con retry automatico.",
            allowed=True,
            payload={"seconds": 30},
        ))

    if "configentryauthfailed" in text or "authentication failed" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Ri-autenticazione richiesta",
            reason="Le credenziali dell'integrazione sembrano scadute o non valide. Serve ri-autenticazione da Impostazioni > Dispositivi e Servizi.",
            allowed=True,
        ))

    if "requirements for" in text and ("not found" in text or "failed" in text):
        actions.append(HealingAction(
            kind="restart_homeassistant",
            title="Restart per reinstallare requirement",
            reason="Home Assistant non ha trovato una libreria Python richiesta. Un restart puo' ritentare l'installazione al boot.",
            allowed=settings.allow_homeassistant_restart,
        ))

    if "invalid config" in text or "configuration.yaml" in text:
        actions.append(HealingAction(
            kind="reload_core_config",
            title="Reload configurazione core",
            reason="Il log punta a configurazione non aggiornata o non ricaricata.",
            allowed=settings.allow_integration_reload,
        ))

    if ("database is locked" in text or "recorder" in issue.source.lower()) and "error" in text:
        actions.append(HealingAction(
            kind="restart_homeassistant",
            title="Restart Home Assistant",
            reason="Errore recorder/database persistente: restart può liberare risorse bloccate.",
            allowed=settings.allow_homeassistant_restart,
        ))

    if "addon" in text and ("crashed" in text or "exit code" in text):
        slug = _extract_addon_slug(text)
        if slug:
            actions.append(HealingAction(
                kind="restart_addon",
                title="Restart add-on",
                reason="Il log indica crash di un add-on specifico.",
                allowed=settings.allow_addon_restart,
                payload={"slug": slug},
            ))

    if not actions:
        known_issue = match_known_issue(text)
        if known_issue:
            actions.append(HealingAction(
                kind="notify_only",
                title=known_issue["title"],
                reason=f"{known_issue['diagnosis']} {known_issue['safe_response']}",
                allowed=True,
            ))

    if not actions:
        actions.append(HealingAction(
            kind="notify_only",
            title="Solo notifica",
            reason="Errore non riconosciuto dai playbook: serve revisione manuale.",
            allowed=True,
        ))

    return actions[: settings.max_actions_per_cycle]


def _extract_entry_id(text: str) -> str | None:
    patterns = [
        r"entry_id[=: ]+([a-z0-9_]+)",
        r"config entry ['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _extract_addon_slug(text: str) -> str | None:
    match = re.search(r"addon[_ /-]+([a-z0-9_]+)", text)
    return match.group(1) if match else None
