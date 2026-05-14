# Home Assistant MCP Self Healer

Add-on Home Assistant autonomo che espone un piccolo server MCP, legge i log di Home Assistant, individua errori ricorrenti, prova remediation conservative e invia una mail con diagnosi e interventi eseguiti.

Autore: **Starace Giuseppe**

Donate PayPal: [staracegiuseppe@gmail.com](https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR)

## Cosa fa

- Si collega a Home Assistant tramite REST API (`SUPERVISOR_TOKEN` negli add-on o Long-Lived Access Token).
- Espone strumenti MCP via JSON-RPC HTTP su `/mcp`.
- Controlla periodicamente i log (`/api/error_log`).
- Classifica gli errori tramite playbook locali.
- Esegue solo azioni consentite dalla configurazione.
- Crea un backup prima di azioni invasive, se richiesto.
- Invia una mail con errore rilevato, decisione presa, risultato e prossimi passi.

## Avvio locale

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python server.py
```

## Add-on Home Assistant

Repository add-on: `https://github.com/staracegiuseppe/ha_mcp_self_healer_addon`.

Copiando questa cartella in un repository add-on o nella cartella `/addons`, Home Assistant può installarlo come add-on locale.

Configura almeno:

- `ha_url`
- `ha_token` se non gira come add-on con `SUPERVISOR_TOKEN`
- `email_enabled`, `email_from`, `email_to`
- per Gmail OAuth2: `oauth2_client_id`, `oauth2_client_secret`, `oauth2_refresh_token`
- come fallback App Password/SMTP: `smtp_host`, `smtp_user`, `smtp_password`

L'invio email segue lo stesso approccio di Market Analyze: prova prima Gmail OAuth2, poi SMTP/App Password.

## Limiti di sicurezza

Questa app non modifica file YAML arbitrari e non fa restart distruttivi senza che l'azione sia abilitata. È volutamente prudente: quando non riconosce un errore, lo segnala via mail invece di improvvisare.
