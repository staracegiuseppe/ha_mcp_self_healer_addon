#!/bin/sh
set -eu

OPTIONS=/data/options.json

get_opt() {
  python3 -c "
import json, os
key='$1'
default='$2'
try:
    with open('${OPTIONS}', encoding='utf-8') as f:
        data=json.load(f)
    value=data.get(key, default)
    print(default if value is None else value)
except Exception:
    print(os.getenv(key.upper(), default))
" 2>/dev/null || echo "$2"
}

export HA_URL="$(get_opt ha_url http://supervisor/core)"
export SUPERVISOR_URL="$(get_opt supervisor_url http://supervisor)"
export HA_TOKEN="$(get_opt ha_token "")"
export CHECK_INTERVAL_SECONDS="$(get_opt check_interval_seconds 300)"
export DRY_RUN="$(get_opt dry_run true)"
export AUTO_FIX_ENABLED="$(get_opt auto_fix_enabled true)"
export NOTIFY_ON_NOOP="$(get_opt notify_on_noop false)"
export CREATE_BACKUP_BEFORE_RESTART="$(get_opt create_backup_before_restart true)"
export ALLOW_HOMEASSISTANT_RESTART="$(get_opt allow_homeassistant_restart false)"
export ALLOW_ADDON_RESTART="$(get_opt allow_addon_restart true)"
export ALLOW_INTEGRATION_RELOAD="$(get_opt allow_integration_reload true)"
export MAX_ACTIONS_PER_CYCLE="$(get_opt max_actions_per_cycle 3)"
export EMAIL_ENABLED="$(get_opt email_enabled false)"
export SMTP_HOST="$(get_opt smtp_host smtp.gmail.com)"
export SMTP_PORT="$(get_opt smtp_port 587)"
export SMTP_TLS="$(get_opt smtp_tls true)"
export SMTP_USER="$(get_opt smtp_user "")"
export SMTP_PASSWORD="$(get_opt smtp_password "")"
export EMAIL_FROM="$(get_opt email_from "")"
export EMAIL_TO="$(get_opt email_to "")"
export OAUTH2_CLIENT_ID="$(get_opt oauth2_client_id "")"
export OAUTH2_CLIENT_SECRET="$(get_opt oauth2_client_secret "")"
export OAUTH2_REFRESH_TOKEN="$(get_opt oauth2_refresh_token "")"
export BIND_HOST=0.0.0.0
export PORT=8124

if [ -z "${HA_TOKEN}" ] && [ -n "${SUPERVISOR_TOKEN:-}" ]; then
  export HA_TOKEN="${SUPERVISOR_TOKEN}"
fi

exec python /app/server.py
