import json
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
        "kind": "reload_integration_by_domain",
        "title": "Reload integrazione per dominio",
        "triggers": ["pychromecast failed to connect", "connection reset by peer"],
        "action": "L'agent cerca i config entry del dominio indicato e chiama homeassistant.reload_config_entry.",
        "safety": "Consentito solo se allow_integration_reload=true. In dry-run viene solo simulato.",
        "improvement_hint": "Associare IP/dispositivo al singolo config entry quando Home Assistant lo espone.",
    },
    {
        "kind": "reload_alexa_exposure",
        "title": "Reload esposizione Alexa/Emulated Hue",
        "triggers": ["emulated_hue entity not found", "alexa discovery stale", "cloud alexa exposure errors"],
        "action": "Ricarica i config entry cloud/emulated_hue quando presenti e poi ricarica la configurazione core.",
        "safety": "Consentito solo se allow_alexa_exposure_reload=true. Non elimina dispositivi da Alexa: quello va fatto dal client se l'entita' e' stata rimossa.",
        "improvement_hint": "Aggiungere update automatico delle exposure quando Home Assistant espone un endpoint REST stabile per Alexa.",
    },
    {
        "kind": "patch_mqtt_bridge_update_state",
        "title": "Patch payload MQTT bridge_update mancante",
        "triggers": ["mqtt.update unable to process payload", "bridge_update missing in value_template"],
        "action": "Ripubblica sul topic state lo stesso JSON con bridge_update di fallback e ricarica MQTT.",
        "safety": "Consentito solo se allow_mqtt_state_patch=true. Aggiunge solo la chiave bridge_update al payload JSON esistente.",
        "improvement_hint": "Correggere a monte il discovery template dell'entita' update per usare value_json.get('bridge_update', {}).",
    },
    {
        "kind": "install_update_by_keyword",
        "title": "Installa update integrazione custom",
        "triggers": ["govee app version too low", "sonoff wrong domain will stop working"],
        "action": "Cerca entita' update.* con keyword dell'integrazione e chiama update.install se lo stato e' on.",
        "safety": "Consentito solo se allow_update_install=true. Installa solo update gia' proposti da Home Assistant.",
        "improvement_hint": "Mappare con piu' precisione repository HACS e changelog prima dell'installazione.",
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
        "kind": "restart_automation",
        "title": "Riavvia automazione bloccata",
        "triggers": ["automation already running"],
        "action": "Chiama automation.turn_off con stop_actions=true e poi automation.turn_on.",
        "safety": "Consentito solo se allow_automation_restart=true. Non lascia l'automazione disabilitata.",
        "improvement_hint": "Valutare mode restart/queued per automazioni che restano spesso in running.",
    },
    {
        "kind": "stop_script",
        "title": "Stop script rimasto in esecuzione",
        "triggers": ["script ... Already running"],
        "action": "Chiama script.turn_off sullo script che risulta ancora running.",
        "safety": "Consentito solo se allow_script_stop=true. In dry-run viene solo simulato.",
        "improvement_hint": "Suggerire anche mode restart/queued quando lo stesso script viene richiamato spesso.",
    },
    {
        "kind": "cleanup_browser_mod_obsolete",
        "title": "Pulizia browser obsoleti Browser Mod",
        "triggers": ["browser_mod missing/not currently available", "homekit 150 device limit con browser_mod"],
        "action": "Rileva i Browser Mod ancora attivi e chiama browser_mod.deregister_browser escludendo quelli vivi.",
        "safety": "Consentito solo se allow_browser_mod_cleanup=true. Non cancella entita' manualmente e non deregistra se non trova almeno un browser attivo.",
        "improvement_hint": "Aggiungere una allowlist di browser fissi, ad esempio tablet a muro, se devono restare registrati anche quando offline.",
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

    if "bridge_update" in text and ("unable to process payload" in text or "template variable error" in text):
        topic = _extract_mqtt_topic(issue.message)
        raw_payload = _extract_mqtt_payload(issue.message)
        patched_payload = _patch_bridge_update_payload(raw_payload)
        if topic and patched_payload:
            actions.append(HealingAction(
                kind="patch_mqtt_bridge_update_state",
                title="Patch MQTT bridge_update mancante",
                reason=(
                    f"Il topic {topic} pubblica uno stato senza bridge_update, ma il template update lo richiede. "
                    "L'agent ripubblica lo stesso payload con bridge_update di fallback e ricarica MQTT."
                ),
                allowed=settings.allow_mqtt_state_patch,
                payload={"topic": topic, "patched_payload": patched_payload},
            ))
        else:
            actions.append(HealingAction(
                kind="reload_integration_by_domain",
                title="Reload MQTT dopo template bridge_update rotto",
                reason="Rilevato template MQTT rotto su bridge_update, ma non riesco a ricostruire topic/payload in sicurezza. Ricarico MQTT.",
                allowed=settings.allow_integration_reload,
                payload={"domain": "mqtt"},
            ))

    if "emulated_hue" in text and "entity not found" in text:
        missing_entity = _extract_missing_entity(text)
        if missing_entity and "browser_mod_" in missing_entity:
            actions.append(HealingAction(
                kind="cleanup_browser_mod_obsolete",
                title="Pulizia Browser Mod obsoleti per Alexa",
                reason=(
                    f"Emulated Hue/Alexa sta chiamando il vecchio Browser Mod {missing_entity}. "
                    "Pulisco le registrazioni Browser Mod obsolete prima di ricaricare l'esposizione."
                ),
                allowed=settings.allow_browser_mod_cleanup,
                payload={"entity_id": missing_entity},
            ))
        actions.append(HealingAction(
            kind="reload_alexa_exposure",
            title="Reload esposizione Alexa/Emulated Hue",
            reason=(
                f"Il client Hue/Alexa sta ancora chiamando {missing_entity or 'una vecchia entita'} non piu' presente in Home Assistant. "
                "L'agent ricarica l'esposizione lato Home Assistant; se Alexa ha ancora il vecchio device in cache, dovra' dimenticarlo e rifare discovery."
            ),
            allowed=settings.allow_alexa_exposure_reload,
            payload={"entity_id": missing_entity} if missing_entity else {},
        ))

    if "alexa" in text and ("discovery" in text or "exposure" in text or "not found" in text or "entity not found" in text):
        actions.append(HealingAction(
            kind="reload_alexa_exposure",
            title="Reload esposizione Alexa",
            reason="Il log indica un problema di discovery/esposizione Alexa. Ricarico Cloud/Emulated Hue e la configurazione core.",
            allowed=settings.allow_alexa_exposure_reload,
        ))

    if "referenced entities" in text and ("missing" in text or "not currently available" in text):
        missing_entity = _extract_referenced_entity(text)
        if "browser_mod" in text:
            actions.append(HealingAction(
                kind="cleanup_browser_mod_obsolete",
                title="Pulizia Browser Mod obsoleti",
                reason=(
                    f"Browser Mod sta lasciando riferimenti non disponibili ({missing_entity or 'entita browser_mod'}). "
                    "L'agent deregistra i browser non attivi mantenendo esclusi quelli ancora vivi."
                ),
                allowed=settings.allow_browser_mod_cleanup,
                payload={"entity_id": missing_entity} if missing_entity else {},
            ))
        else:
            actions.append(HealingAction(
                kind="notify_only",
                title="Entita' referenziata mancante",
                reason=(
                    f"Una automazione/script/dashboard sta usando {missing_entity or 'una entita'} non disponibile. "
                    "Aggiungi una guard condition, correggi il riferimento o usa continue_on_error se l'azione non deve bloccare la sequenza."
                ),
                allowed=True,
                payload={"entity_id": missing_entity} if missing_entity else {},
            ))

    if "browser_mod" in text and "150 device limit" in text:
        actions.append(HealingAction(
            kind="cleanup_browser_mod_obsolete",
            title="Pulizia Browser Mod per limite HomeKit",
            reason="HomeKit ha superato il limite di 150 device anche per vecchi browser Browser Mod. Pulisco le registrazioni obsolete conservando i browser attivi.",
            allowed=settings.allow_browser_mod_cleanup,
        ))

    if "no update available" in text and "update.ha_mcp_self_healer_update" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Update add-on non disponibile",
            reason="Home Assistant ha provato a installare update.ha_mcp_self_healer_update ma non c'era nessun update disponibile. Serve aggiornare lo store/rebuildare l'add-on, non chiamare update.install.",
            allowed=True,
        ))

    if "xiaomi tv" in text and "could not find" in text:
        actions.append(HealingAction(
            kind="reload_integration_by_domain",
            title="Reload Xiaomi TV",
            reason="Xiaomi TV non e' stato trovato all'IP configurato. Ricarico l'integrazione per riprovare discovery/connessione.",
            allowed=settings.allow_integration_reload,
            payload={"domain": "xiaomi_tv"},
        ))

    if "govee" in text and ("app version is too low" in text or "no token available" in text or "login failed" in text):
        actions.append(HealingAction(
            kind="install_update_by_keyword",
            title="Aggiorna integrazione Govee",
            reason="Govee rifiuta login per app version troppo bassa: provo a installare l'update HACS/integrazione se disponibile.",
            allowed=settings.allow_update_install,
            payload={"keyword": "govee"},
        ))
        actions.append(HealingAction(
            kind="reload_integration_by_domain",
            title="Reload Govee",
            reason="Dopo il tentativo update, ricarico Govee per rigenerare token/sessione.",
            allowed=settings.allow_integration_reload,
            payload={"domain": "govee"},
        ))

    if "sonoff" in text and "sets an entity id with wrong domain" in text:
        actions.append(HealingAction(
            kind="install_update_by_keyword",
            title="Aggiorna SonoffLAN",
            reason="SonoffLAN sta creando entity_id con dominio errato; provo a installare update disponibile dell'integrazione.",
            allowed=settings.allow_update_install,
            payload={"keyword": "sonoff"},
        ))
        actions.append(HealingAction(
            kind="reload_integration_by_domain",
            title="Reload Sonoff",
            reason="Ricarico Sonoff dopo il tentativo update per ricreare le entita' col dominio corretto se l'integrazione lo supporta.",
            allowed=settings.allow_integration_reload,
            payload={"domain": "sonoff"},
        ))

    if "generic platform for the camera integration does not support platform setup" in text:
        actions.append(HealingAction(
            kind="reload_core_config",
            title="Reload configurazione camera",
            reason="La configurazione camera usa platform generic in modo non piu' supportato. Ricarico core config; se persiste serve migrare YAML a camera: - platform: generic.",
            allowed=settings.allow_integration_reload,
        ))

    if "platform automation does not generate unique ids" in text and "already exists" in text:
        actions.append(HealingAction(
            kind="reload_core_config",
            title="Reload automazioni per unique_id duplicato",
            reason="Home Assistant segnala automazione duplicata per unique_id gia' esistente. Ricarico core config; la correzione definitiva e' rimuovere/rigenerare il duplicato YAML.",
            allowed=settings.allow_integration_reload,
        ))

    if "already running" in text and "homeassistant.components.automation." in text:
        automation_entity = _automation_entity_from_source(issue.source)
        if automation_entity:
            actions.append(HealingAction(
                kind="restart_automation",
                title=f"Riavvia automazione bloccata {automation_entity}",
                reason="L'automazione risulta gia' in esecuzione. La fermo con stop_actions=true e la riattivo subito.",
                allowed=settings.allow_automation_restart,
                payload={"entity_id": automation_entity},
            ))

    if "installing a specific version is not supported" in text and "update.ha_mcp_self_healer_update" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Update add-on con versione specifica non supportato",
            reason="L'entita' update dell'add-on non supporta installazione di versioni specifiche. Usare update normale dopo refresh dello store o rebuild manuale.",
            allowed=True,
        ))

    if "invalidstateerror" in text and ("async_remove" in text or "async_reset" in text):
        actions.append(HealingAction(
            kind="notify_only",
            title="InvalidStateError core/entity platform",
            reason="Traceback orfano rilevato durante rimozione/reset entita'. E' spesso un bug transitorio di HA o integrazione; se ricorre, serve identificare l'integrazione immediatamente precedente nei log.",
            allowed=True,
        ))

    if "already running" in text and "homeassistant.components.script." in text:
        script_entity = _script_entity_from_source(issue.source)
        if script_entity:
            actions.append(HealingAction(
                kind="stop_script",
                title=f"Ferma {script_entity}",
                reason="Lo script risulta gia' in esecuzione e sta rifiutando nuove chiamate. Lo stop sblocca lo stato running; poi conviene valutare mode restart o queued.",
                allowed=settings.allow_script_stop,
                payload={"entity_id": script_entity},
            ))

    if "failed to setup triggers and has been disabled" in text and ("unknown entity" in text or "unknown entity registry entry" in text):
        alias = _extract_automation_alias(text)
        automation_entity = _automation_entity_from_alias(alias) if alias else None
        actions.append(HealingAction(
            kind="disable_automation" if automation_entity else "notify_only",
            title=f"Conferma stop automazione rotta{f' {automation_entity}' if automation_entity else ''}",
            reason=(
                f"L'automazione {alias or 'indicata nel log'} ha trigger verso entita' inesistenti ed e' stata disabilitata da Home Assistant. "
                "La correzione strutturale e' sostituire il trigger con una entity_id valida o rimuovere l'automazione."
            ),
            allowed=settings.allow_automation_disable if automation_entity else True,
            payload={"entity_id": automation_entity} if automation_entity else {},
        ))

    if "does not support action" in text:
        entity_id, service = _extract_unsupported_service(text)
        actions.append(HealingAction(
            kind="notify_only",
            title="Servizio non supportato dall'entita'",
            reason=(
                f"{entity_id or 'Una entita'} non supporta {service or 'il servizio richiesto'}. "
                "Aggiorna automazioni/script sostituendo il servizio con uno supportato o controllando supported_features."
            ),
            allowed=True,
            payload={"entity_id": entity_id, "service": service},
        ))

    if "error from stream worker" in text and "stream ended" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Stream camera terminato",
            reason="Lo stream RTSP/camera e' terminato senza pacchetti. Verificare stabilita' camera/rete o configurazione go2rtc; non c'e' una remediation HA sicura senza sapere quale camera riavviare.",
            allowed=True,
        ))

    if "go2rtc" in text and ("i/o timeout" in text or "error=eof" in text or "rtsp://" in text):
        actions.append(HealingAction(
            kind="notify_only",
            title="Timeout go2rtc/RTSP",
            reason="go2rtc non riceve dati dal flusso RTSP. Controllare camera, credenziali, rete e profilo stream; eventuale restart add-on richiede mapping dello slug.",
            allowed=True,
        ))

    if "pychromecast.socket_client" in text or "async_upnp_client" in text:
        if "pychromecast.socket_client" in text:
            actions.append(HealingAction(
                kind="reload_integration_by_domain",
                title="Reload integrazione Cast",
                reason="pychromecast segnala connessione persa. L'agent provera' a risolvere il config entry del dominio cast e fare reload.",
                allowed=settings.allow_integration_reload,
                payload={"domain": "cast"},
            ))
        else:
            actions.append(HealingAction(
                kind="notify_only",
                title="Dispositivo media non raggiungibile",
                reason="DLNA/UPnP non risponde o resetta la connessione. Verificare IP fisso, standby del TV e connettivita' LAN.",
                allowed=True,
            ))

    if "ezviz" in text and ("invalid response from api" in text or "does not support action" in text):
        actions.append(HealingAction(
            kind="notify_only",
            title="EZVIZ API o servizio non valido",
            reason="EZVIZ restituisce risposta API non valida oppure l'entita' non supporta il servizio richiesto. Serve verificare credenziali/rate limit e correggere automazioni che chiamano servizi non supportati.",
            allowed=True,
        ))

    if "upload failed for synology_dsm" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Backup Synology fallito",
            reason="Il caricamento backup su Synology DSM e' fallito. Verificare spazio, permessi, connessione DSM e credenziali; non viene cancellato nulla automaticamente.",
            allowed=True,
        ))

    if "failed to to call /store/repositories" in text and "could not read username" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Repository add-on Git non accessibile",
            reason="Supervisor non riesce a clonare il repository add-on: sembra privato, errato o non accessibile senza credenziali. Rimuovere il vecchio repository e usare quello pubblico corretto.",
            allowed=True,
        ))

    if "no update available for app" in text and "ha_mcp_self_healer" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Update add-on richiesto ma non disponibile",
            reason="Supervisor segnala che non esiste un update disponibile per HA MCP Self Healer. Aggiornare/rebuildare lo store add-on prima di riprovare.",
            allowed=True,
        ))

    if "does not generate unique ids" in text and "already exists" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Unique ID duplicato",
            reason="Home Assistant sta ignorando una entita' duplicata per unique_id gia' esistente. Se persiste dopo reload/restart, va rimossa o rinominata la definizione duplicata.",
            allowed=True,
        ))

    if "app config 'arch' uses deprecated values" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Architetture add-on deprecate",
            reason="Supervisor segnala architetture deprecate nel config di un add-on. Per HA MCP Self Healer e' stato corretto rimuovendo armhf/armv7; per add-on terzi serve update del maintainer.",
            allowed=True,
        ))

    if "deprecated 'codenotary' field" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Campo codenotary deprecato",
            reason="Il campo codenotary non viene piu' usato dal Supervisor. Non rompe l'avvio, ma va rimosso dal config dell'add-on dal rispettivo maintainer.",
            allowed=True,
        ))

    if "deprecated 'advanced' field" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Campo advanced deprecato",
            reason="Il campo advanced e' ignorato dal Supervisor moderno. Non blocca l'avvio, ma va rimosso dal config dell'add-on dal maintainer.",
            allowed=True,
        ))

    if "has full device access, and selective device access" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Accesso dispositivi add-on ridondante",
            reason="Supervisor segnala che un add-on usa sia full device access sia device access selettivo. Non blocca l'avvio, ma il maintainer dovrebbe scegliere un solo modello.",
            allowed=True,
        ))

    if "error websocket message received while proxying" in text and "cannot write to closing transport" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Proxy WebSocket chiuso dal client",
            reason="Supervisor stava proxyando un WebSocket verso un add-on, ma il client ha chiuso la connessione. Se isolato e' innocuo; se ricorrente verificare add-on e rete/client.",
            allowed=True,
        ))

    if "failed to validate image signature" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Firma immagine Docker non validabile",
            reason="Il daemon Docker non riesce a validare la firma dell'immagine per manifest non atteso. Verificare add-on/immagine e aggiornamenti Supervisor; non cancello immagini automaticamente.",
            allowed=True,
        ))

    if "forcibly turning on oci-mediatype mode for attestations" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="BuildKit OCI mediatype informativo",
            reason="BuildKit ha forzato OCI mediatype per le attestazioni. Se la build si conclude, e' rumore informativo.",
            allowed=True,
        ))

    if "error reading preface" in text and "docker.sock" in text:
        actions.append(HealingAction(
            kind="notify_only",
            title="Connessione Docker socket resettata",
            reason="Una connessione locale al Docker socket e' stata chiusa durante build/update. Se isolata non richiede fix; se ricorrente va verificato il ciclo di build.",
            allowed=True,
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


def _extract_mqtt_topic(message: str) -> str | None:
    match = re.search(r"for topic\s+([^,\s]+)", message)
    return match.group(1).strip("'\"") if match else None


def _extract_mqtt_payload(message: str) -> str | None:
    match = re.search(r"payload\s+'({.*?})'\s+for topic", message)
    return match.group(1) if match else None


def _patch_bridge_update_payload(raw_payload: str | None) -> str | None:
    if not raw_payload:
        return None
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("bridge_update"), dict):
        return json.dumps(payload, separators=(",", ":"))
    payload["bridge_update"] = {
        "installed_version": "unknown",
        "latest_version": "unknown",
        "state": "idle",
        "progress": 0,
    }
    return json.dumps(payload, separators=(",", ":"))


def _extract_addon_slug(text: str) -> str | None:
    match = re.search(r"addon[_ /-]+([a-z0-9_]+)", text)
    return match.group(1) if match else None


def _extract_missing_entity(text: str) -> str | None:
    match = re.search(r"entity not found:\s*([a-z0-9_]+\.[a-z0-9_]+)", text)
    return match.group(1) if match else None


def _extract_referenced_entity(text: str) -> str | None:
    match = re.search(r"referenced entities\s+([a-z0-9_]+\.[a-z0-9_]+)", text)
    return match.group(1) if match else None


def _script_entity_from_source(source: str) -> str | None:
    prefix = "homeassistant.components.script."
    if not source.startswith(prefix):
        return None
    object_id = source.removeprefix(prefix).strip()
    return f"script.{object_id}" if object_id else None


def _automation_entity_from_source(source: str) -> str | None:
    prefix = "homeassistant.components.automation."
    if not source.startswith(prefix):
        return None
    object_id = source.removeprefix(prefix).strip()
    return f"automation.{object_id}" if object_id else None


def _extract_automation_alias(text: str) -> str | None:
    match = re.search(r"automation with alias ['\"]([^'\"]+)['\"] failed to setup", text)
    return match.group(1).strip() if match else None


def _automation_entity_from_alias(alias: str) -> str:
    object_id = re.sub(r"[^a-z0-9_]+", "_", alias.lower().strip())
    object_id = re.sub(r"_+", "_", object_id).strip("_")
    return f"automation.{object_id}"


def _extract_unsupported_service(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"entity\s+([a-z0-9_]+\.[a-z0-9_]+)\s+does not support action\s+([a-z0-9_]+\.[a-z0-9_]+)", text)
    if match:
        return match.group(1), match.group(2)
    return None, None
