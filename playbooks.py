import re

from config import Settings
from models import HealingAction, LogIssue


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
