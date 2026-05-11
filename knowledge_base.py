KNOWN_ISSUES = [
    {
        "category": "Setup integrazione",
        "title": "ConfigEntryNotReady / platform not ready / will retry",
        "patterns": ["configentrynotready", "platform not ready", "will retry"],
        "diagnosis": "Il dispositivo o servizio non e' raggiungibile durante il caricamento. Home Assistant di solito ritenta automaticamente.",
        "safe_response": "Attesa e ricontrollo; se persiste, verificare rete, alimentazione o disponibilita' del servizio.",
        "automation_level": "safe",
    },
    {
        "category": "Setup integrazione",
        "title": "ConfigEntryAuthFailed / authentication failed",
        "patterns": ["configentryauthfailed", "authentication failed", "reauthentication"],
        "diagnosis": "Le credenziali o il token dell'integrazione non sono piu' validi.",
        "safe_response": "Solo notifica: serve ri-autenticazione da Impostazioni > Dispositivi e Servizi.",
        "automation_level": "manual",
    },
    {
        "category": "Setup integrazione",
        "title": "ConfigEntryError / error setting up entry",
        "patterns": ["configentryerror", "error setting up entry", "error setting up config entry"],
        "diagnosis": "Errore permanente di setup: configurazione corrotta, incompatibilita' o bug di integrazione.",
        "safe_response": "Reload config entry se viene rilevato un entry_id; altrimenti solo notifica.",
        "automation_level": "guarded",
    },
    {
        "category": "Setup integrazione",
        "title": "Requirements for X not found",
        "patterns": ["requirements for", "not found", "failed to install requirement"],
        "diagnosis": "Una libreria Python richiesta dall'integrazione non si e' installata correttamente.",
        "safe_response": "Solo notifica, oppure restart Home Assistant se esplicitamente autorizzato.",
        "automation_level": "guarded",
    },
    {
        "category": "YAML e configurazione",
        "title": "Indentazione errata / tab YAML",
        "patterns": ["found character that cannot start any token", "found character that can't start any token", "scannererror", "while scanning for the next token"],
        "diagnosis": "Il YAML contiene tab o indentazione non valida.",
        "safe_response": "Solo notifica con indicazione di eseguire Configuration Check prima del riavvio.",
        "automation_level": "manual",
    },
    {
        "category": "YAML e configurazione",
        "title": "Entity name con caratteri speciali",
        "patterns": ["invalid entity id", "invalid slug", "entity_id is an invalid entity id"],
        "diagnosis": "Un entity_id o nome configurato non rispetta il formato atteso da Home Assistant.",
        "safe_response": "Solo notifica: serve correzione nome/entity_id o rename controllato.",
        "automation_level": "manual",
    },
    {
        "category": "Automazioni",
        "title": "Automazione che non scatta o si ferma",
        "patterns": ["condition did not pass", "stopped because", "automation trace", "unknown service"],
        "diagnosis": "Il trace dell'automazione e' il punto migliore per capire trigger, condizioni e step falliti.",
        "safe_response": "Solo notifica con richiesta di controllare Settings > Automations > Traces.",
        "automation_level": "manual",
    },
    {
        "category": "Automazioni",
        "title": "Trigger da ritorno unavailable",
        "patterns": ["from unavailable", "unavailable to", "state changed from unavailable"],
        "diagnosis": "Un trigger di stato puo' partire quando l'entita' torna da unavailable a uno stato normale.",
        "safe_response": "Solo notifica: suggerisce not_from: unavailable o condizione di esclusione.",
        "automation_level": "manual",
    },
    {
        "category": "Automazioni",
        "title": "Azione bloccata da entita' non disponibile",
        "patterns": ["referenced entities", "not available", "entity not available", "not found"],
        "diagnosis": "Una sequenza puo' fermarsi se una entita' controllata non esiste o non e' disponibile.",
        "safe_response": "Solo notifica: suggerisce guard condition o continue_on_error.",
        "automation_level": "manual",
    },
    {
        "category": "Automazioni",
        "title": "Loop di riavvio causato da automazione",
        "patterns": ["hassio.reboot", "homeassistant.restart", "restart loop", "reboot loop"],
        "diagnosis": "Una automazione che riavvia senza resettare il trigger puo' creare un loop di reboot.",
        "safe_response": "Solo notifica; lo stop automatico richiede rilevamento loop e allow_automation_disable=true.",
        "automation_level": "guarded",
    },
    {
        "category": "Automazioni",
        "title": "Setup automazione fallito o timeout salvataggio",
        "patterns": ["new automation setup failed", "waiting for it to setup has timed out", "automation setup failed"],
        "diagnosis": "Il reload automazioni puo' fallire per errori YAML o configurazione non valida.",
        "safe_response": "Solo notifica con suggerimento Configuration Check.",
        "automation_level": "manual",
    },
    {
        "category": "Luci e dispositivi",
        "title": "Toggle loop / stato luce non sincronizzato",
        "patterns": ["light.toggle", "toggle", "state not updated", "oscillation"],
        "diagnosis": "L'uso di toggle con stato non sincronizzato puo' invertire il comando nei cicli successivi.",
        "safe_response": "Rilevamento live delle oscillazioni; suggerisce turn_on/turn_off espliciti o update_entity.",
        "automation_level": "guarded",
    },
    {
        "category": "Luci e dispositivi",
        "title": "light.turn_on fallisce con Unknown error",
        "patterns": ["light.turn_on", "unknown error", "template light"],
        "diagnosis": "Una luce template o integrazione luce puo' non accettare piu' il comando dopo aggiornamenti.",
        "safe_response": "Solo notifica: verificare template e log dell'integrazione.",
        "automation_level": "manual",
    },
    {
        "category": "Luci e dispositivi",
        "title": "Entita' unavailable anche se dispositivo acceso",
        "patterns": ["unavailable", "device stopped responding", "entity is unavailable"],
        "diagnosis": "Il dispositivo puo' avere segnale debole o connettivita' instabile; le automazioni rischiano di fermarsi.",
        "safe_response": "Solo notifica: suggerisce wait_template/guard condition e miglioramento mesh o rete.",
        "automation_level": "manual",
    },
    {
        "category": "Zigbee",
        "title": "Tutti i dispositivi Zigbee unavailable",
        "patterns": ["all attempts have failed", "timeouterror", "zha", "zigbee"],
        "diagnosis": "Possibile perdita del coordinatore Zigbee, interferenza USB 3.0 o dongle instabile.",
        "safe_response": "Solo notifica; restart HA solo se abilitato esplicitamente.",
        "automation_level": "guarded",
    },
    {
        "category": "Zigbee",
        "title": "Dongle conteso tra ZHA e Zigbee2MQTT",
        "patterns": ["serial", "ezsp", "failed to connect", "adapter", "zigbee2mqtt"],
        "diagnosis": "Il dongle puo' essere conteso o non raggiungibile dal coordinatore scelto.",
        "safe_response": "Solo notifica: verificare ZHA/Z2M e assegnazione del dispositivo.",
        "automation_level": "manual",
    },
    {
        "category": "Zigbee",
        "title": "Entita' MQTT/Z2M non piu' fornita",
        "patterns": ["no longer being provided by the mqtt integration", "mqtt integration"],
        "diagnosis": "Disallineamento tra entita' registrata in HA e nome/ID pubblicato da Zigbee2MQTT.",
        "safe_response": "Solo notifica: rinominare in Z2M o ricreare l'entita' in HA.",
        "automation_level": "manual",
    },
    {
        "category": "Rete e connettivita'",
        "title": "Connect call failed / device stopped responding",
        "patterns": ["connect call failed", "device stopped responding", "connection refused", "host is unreachable"],
        "diagnosis": "Il dispositivo LAN non e' raggiungibile, spesso per IP cambiato o rete instabile.",
        "safe_response": "Solo notifica: suggerisce DHCP reservation o IP statico.",
        "automation_level": "manual",
    },
    {
        "category": "Rete e connettivita'",
        "title": "CPU al 100% / Home Assistant non raggiungibile",
        "patterns": ["blocked for", "executor", "cpu", "bootstrap", "taking over"],
        "diagnosis": "Una integrazione puo' bloccare il setup o saturare la coda task.",
        "safe_response": "Solo notifica; disabilitare integrazione richiede decisione manuale.",
        "automation_level": "manual",
    },
]


def list_known_issues() -> list[dict]:
    return list(KNOWN_ISSUES)


def match_known_issue(text: str) -> dict | None:
    lowered = text.lower()
    best: dict | None = None
    best_score = 0
    for issue in KNOWN_ISSUES:
        score = sum(1 for pattern in issue["patterns"] if pattern in lowered)
        if score > best_score:
            best = issue
            best_score = score
    return best
