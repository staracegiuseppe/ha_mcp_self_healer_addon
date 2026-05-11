from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from config import Settings
from models import HealingAction, LogIssue

OSCILLATING_DOMAINS = {"light", "switch", "fan", "cover"}
OSCILLATING_STATES = {"on", "off", "open", "closed"}


def detect_loops(entries: list[dict[str, Any]], settings: Settings) -> list[tuple[LogIssue, list[HealingAction]]]:
    if not settings.loop_monitor_enabled:
        return []

    automation_counts: Counter[str] = Counter()
    state_changes: dict[str, list[str]] = defaultdict(list)

    for entry in entries:
        entity_id = str(entry.get("entity_id") or "")
        state = str(entry.get("state") or "").lower()
        if not entity_id or "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        if domain == "automation":
            automation_counts[entity_id] += 1
        if domain in OSCILLATING_DOMAINS and state in OSCILLATING_STATES:
            state_changes[entity_id].append(state)

    findings: list[tuple[LogIssue, list[HealingAction]]] = []

    for entity_id, count in automation_counts.most_common():
        if count < settings.loop_automation_threshold:
            continue
        issue = _issue(
            "automation_loop",
            entity_id,
            f"Possibile loop automazione: {entity_id} e' comparsa {count} volte nel logbook negli ultimi {settings.loop_window_minutes} minuti.",
            "homeassistant.automation.loop_detector",
        )
        findings.append((issue, [_disable_action(entity_id, settings, "Automazione ripetuta troppe volte nella finestra live.")]))

    noisy_entities = []
    for entity_id, states in state_changes.items():
        if len(states) < settings.loop_toggle_threshold:
            continue
        if len(set(states)) < 2:
            continue
        noisy_entities.append((entity_id, len(states), states))

    likely_automation_actions = [
        _disable_action(entity_id, settings, "Automazione correlata a oscillazioni ripetute di luci/switch.")
        for entity_id, count in automation_counts.most_common(3)
        if count >= 2
    ]

    for entity_id, count, states in noisy_entities:
        issue = _issue(
            "entity_oscillation",
            entity_id,
            f"Possibile loop dispositivo: {entity_id} ha cambiato stato {count} volte negli ultimi {settings.loop_window_minutes} minuti ({', '.join(states[-8:])}).",
            "homeassistant.entity.loop_detector",
        )
        actions = likely_automation_actions or [
            HealingAction(
                kind="notify_only",
                title="Solo notifica loop dispositivo",
                reason="Oscillazione rilevata, ma nessuna automazione correlata e' abbastanza evidente da fermare in sicurezza.",
                allowed=True,
                payload={"entity_id": entity_id, "changes": count},
            )
        ]
        findings.append((issue, actions))

    return findings


def _issue(kind: str, entity_id: str, message: str, source: str) -> LogIssue:
    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    return LogIssue(
        fingerprint=f"{kind}:{entity_id}:{bucket}",
        severity="critical",
        source=source,
        message=message,
    )


def _disable_action(entity_id: str, settings: Settings, reason: str) -> HealingAction:
    return HealingAction(
        kind="disable_automation",
        title=f"Disattiva {entity_id}",
        reason=reason,
        allowed=settings.allow_automation_disable,
        payload={"entity_id": entity_id},
    )
