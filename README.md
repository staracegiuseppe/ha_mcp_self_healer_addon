# Home Assistant MCP Self Healer

![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5)
![MCP](https://img.shields.io/badge/MCP-enabled-1f6feb)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Donate](https://img.shields.io/badge/Donate-PayPal-0070ba)

Add-on Home Assistant autonomo che espone un piccolo server MCP, legge i log di Home Assistant, individua errori ricorrenti, prova remediation conservative e invia una mail con diagnosi e interventi eseguiti.

Autore: **Starace Giuseppe**

Donate PayPal: [staracegiuseppe@gmail.com](https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR)

## Installa

[![Open your Home Assistant instance and show the add add-on repository dialog with this repository pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fstaracegiuseppe%2Fha_mcp_self_healer_addon)

Repository add-on:

```text
https://github.com/staracegiuseppe/ha_mcp_self_healer_addon
```

## Cosa fa

- Si collega a Home Assistant tramite REST API (`SUPERVISOR_TOKEN` negli add-on o Long-Lived Access Token).
- Espone strumenti MCP via JSON-RPC HTTP su `/mcp`.
- Controlla periodicamente i log (`/api/error_log`).
- Classifica gli errori tramite playbook locali.
- Esegue solo azioni consentite dalla configurazione.
- Mostra una plancia salute componenti su `/dashboard`, con stato globale, componenti critici, fix automatici abilitati e ultimi eventi.
- Crea un backup prima di azioni invasive, se richiesto.
- Invia una mail con errore rilevato, decisione presa, risultato e prossimi passi.
- Pulisce Browser Mod obsoleti, ricarica esposizione Alexa/Emulated Hue, patcha payload MQTT noti, riavvia automazioni bloccate e ricarica integrazioni quando il playbook lo consente.
- Espone `ha_list_self_healer_capabilities` e `ha_home_control_dashboard_template` via MCP per descrivere capacita', metodo e template della plancia casa.
- Classifica anche LocalTuya `state_on`, Fully Kiosk/REST offline, camera ONVIF non raggiungibile, Blink/DNS cloud e backup Synology.

## Perché usarlo

Home Assistant spesso non "si rompe" in modo evidente: produce errori nei log, entità non disponibili, automazioni bloccate e integrazioni che smettono di autenticarsi. Questo add-on riduce il tempo tra errore, diagnosi e azione correttiva.

È pensato per:

- utenti avanzati Home Assistant;
- installatori smart home;
- B&B, piccoli hotel, uffici e dashboard sempre accese;
- impianti con Zigbee, MQTT, Browser Mod, Alexa, Sonoff, Govee, camera e automazioni complesse.

## Avvio locale

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python server.py
```

## Add-on Home Assistant

Puoi installarlo come repository add-on Home Assistant usando il pulsante sopra oppure aggiungendo manualmente l'URL del repository.

Configura almeno:

- `ha_url`
- `ha_token` se non gira come add-on con `SUPERVISOR_TOKEN`
- `email_enabled`, `email_from`, `email_to`
- per Gmail OAuth2: `oauth2_client_id`, `oauth2_client_secret`, `oauth2_refresh_token`
- come fallback App Password/SMTP: `smtp_host`, `smtp_user`, `smtp_password`

L'invio email segue lo stesso approccio di Market Analyze: prova prima Gmail OAuth2, poi SMTP/App Password.

## Supporta il progetto

Se HA MCP Self Healer ti fa risparmiare tempo o ti evita downtime, puoi supportare lo sviluppo:

- Donate PayPal: [staracegiuseppe@gmail.com](https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR)
- Supporto prioritario e sviluppo playbook personalizzati: `staracegiuseppe@gmail.com`

## Supporto professionale

Per installatori, aziende e utenti con impianti complessi:

- review rapida log Home Assistant;
- sessione remota di diagnosi;
- playbook personalizzati per errori ricorrenti;
- setup reliability per case, B&B, uffici e dashboard always-on.

Prezzi suggeriti e dettagli: [SUPPORT.md](SUPPORT.md)

## Troubleshooting update add-on

Se Home Assistant mostra:

```text
Error updating HA MCP Self Healer: 'AppManager.update' blocked from execution, no host internet connection
```

il problema non è il codice dell'add-on: il Supervisor sta bloccando l'update perché l'host Home Assistant non vede internet.

Controlli consigliati:

1. Apri **Settings > System > Network** e verifica gateway e DNS.
2. Apri **Settings > System > Repairs** e controlla eventuali problemi di connettività.
3. Verifica che Home Assistant possa raggiungere GitHub e Docker registry.
4. Se usi DNS personalizzati, prova temporaneamente `1.1.1.1` o `8.8.8.8`.
5. Dopo aver ripristinato la rete, fai refresh dello store add-on e rilancia l'update.

La self-healer riconosce questo errore e lo segnala come problema rete/Supervisor, perché non può forzare un update quando il Supervisor lo blocca per assenza di internet host.

## Limiti di sicurezza

Questa app non modifica file YAML arbitrari e non fa restart distruttivi senza che l'azione sia abilitata. È volutamente prudente: quando non riconosce un errore, lo segnala via mail invece di improvvisare.

## Roadmap commerciale

Vedi [MARKETING.md](MARKETING.md) per posizionamento, canali di lancio e idee di monetizzazione.
