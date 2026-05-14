import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field

DEFAULT_IGNORED_PATTERNS = [
    "No update available",
    "Installing a specific version is not supported",
]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return _bool_value(raw, default)


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class Settings(BaseModel):
    ha_url: str = "http://supervisor/core"
    supervisor_url: str = "http://supervisor"
    ha_token: str = ""
    supervisor_token: str = ""
    check_interval_seconds: int = 300
    dry_run: bool = True
    auto_fix_enabled: bool = True
    notify_on_noop: bool = False
    create_backup_before_restart: bool = True
    allow_homeassistant_restart: bool = False
    allow_addon_restart: bool = True
    allow_integration_reload: bool = True
    allow_automation_disable: bool = False
    allow_automation_restart: bool = True
    allow_script_stop: bool = True
    allow_browser_mod_cleanup: bool = True
    allow_alexa_exposure_reload: bool = True
    allow_mqtt_state_patch: bool = True
    allow_update_install: bool = True
    loop_monitor_enabled: bool = True
    loop_window_minutes: int = 5
    loop_toggle_threshold: int = 8
    loop_automation_threshold: int = 6
    seen_ttl_hours: int = 6
    max_actions_per_cycle: int = 10
    ignored_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_IGNORED_PATTERNS))
    email_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""
    oauth2_client_id: str = ""
    oauth2_client_secret: str = ""
    oauth2_refresh_token: str = ""
    bind_host: str = "0.0.0.0"
    port: int = 8124


def _load_options_file() -> dict[str, Any]:
    path = Path("/data/options.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_settings() -> Settings:
    load_dotenv()
    opts = _load_options_file()
    supervisor_token = os.getenv("SUPERVISOR_TOKEN", "")
    ha_url = opts.get("ha_url") or os.getenv("HA_URL", "http://supervisor/core")
    configured_token = opts.get("ha_token") or os.getenv("HA_TOKEN", "")
    token = supervisor_token if ha_url.rstrip("/") == "http://supervisor/core" else (configured_token or supervisor_token)
    return Settings(
        ha_url=ha_url,
        supervisor_url=opts.get("supervisor_url") or os.getenv("SUPERVISOR_URL", "http://supervisor"),
        ha_token=token,
        supervisor_token=supervisor_token,
        check_interval_seconds=int(opts.get("check_interval_seconds") or os.getenv("CHECK_INTERVAL_SECONDS", "300")),
        dry_run=_bool_value(opts.get("dry_run"), _bool_env("DRY_RUN", True)),
        auto_fix_enabled=_bool_value(opts.get("auto_fix_enabled"), _bool_env("AUTO_FIX_ENABLED", True)),
        notify_on_noop=_bool_value(opts.get("notify_on_noop"), _bool_env("NOTIFY_ON_NOOP", False)),
        create_backup_before_restart=_bool_value(opts.get("create_backup_before_restart"), _bool_env("CREATE_BACKUP_BEFORE_RESTART", True)),
        allow_homeassistant_restart=_bool_value(opts.get("allow_homeassistant_restart"), _bool_env("ALLOW_HOMEASSISTANT_RESTART", False)),
        allow_addon_restart=_bool_value(opts.get("allow_addon_restart"), _bool_env("ALLOW_ADDON_RESTART", True)),
        allow_integration_reload=_bool_value(opts.get("allow_integration_reload"), _bool_env("ALLOW_INTEGRATION_RELOAD", True)),
        allow_automation_disable=_bool_value(opts.get("allow_automation_disable"), _bool_env("ALLOW_AUTOMATION_DISABLE", False)),
        allow_automation_restart=_bool_value(opts.get("allow_automation_restart"), _bool_env("ALLOW_AUTOMATION_RESTART", True)),
        allow_script_stop=_bool_value(opts.get("allow_script_stop"), _bool_env("ALLOW_SCRIPT_STOP", True)),
        allow_browser_mod_cleanup=_bool_value(opts.get("allow_browser_mod_cleanup"), _bool_env("ALLOW_BROWSER_MOD_CLEANUP", True)),
        allow_alexa_exposure_reload=_bool_value(opts.get("allow_alexa_exposure_reload"), _bool_env("ALLOW_ALEXA_EXPOSURE_RELOAD", True)),
        allow_mqtt_state_patch=_bool_value(opts.get("allow_mqtt_state_patch"), _bool_env("ALLOW_MQTT_STATE_PATCH", True)),
        allow_update_install=_bool_value(opts.get("allow_update_install"), _bool_env("ALLOW_UPDATE_INSTALL", True)),
        loop_monitor_enabled=_bool_value(opts.get("loop_monitor_enabled"), _bool_env("LOOP_MONITOR_ENABLED", True)),
        loop_window_minutes=int(opts.get("loop_window_minutes") or os.getenv("LOOP_WINDOW_MINUTES", "5")),
        loop_toggle_threshold=int(opts.get("loop_toggle_threshold") or os.getenv("LOOP_TOGGLE_THRESHOLD", "8")),
        loop_automation_threshold=int(opts.get("loop_automation_threshold") or os.getenv("LOOP_AUTOMATION_THRESHOLD", "6")),
        seen_ttl_hours=int(opts.get("seen_ttl_hours") or os.getenv("SEEN_TTL_HOURS", "6")),
        max_actions_per_cycle=int(opts.get("max_actions_per_cycle") or os.getenv("MAX_ACTIONS_PER_CYCLE", "10")),
        ignored_patterns=list(opts.get("ignored_patterns") or DEFAULT_IGNORED_PATTERNS),
        email_enabled=_bool_value(opts.get("email_enabled"), _bool_env("EMAIL_ENABLED", False)),
        smtp_host=opts.get("smtp_host") or os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(opts.get("smtp_port") or os.getenv("SMTP_PORT", "587")),
        smtp_tls=_bool_value(opts.get("smtp_tls"), _bool_env("SMTP_TLS", True)),
        smtp_user=opts.get("smtp_user") or os.getenv("SMTP_USER", ""),
        smtp_password=opts.get("smtp_password") or os.getenv("SMTP_PASSWORD", ""),
        email_from=opts.get("email_from") or os.getenv("EMAIL_FROM", ""),
        email_to=opts.get("email_to") or os.getenv("EMAIL_TO", ""),
        oauth2_client_id=opts.get("oauth2_client_id") or os.getenv("OAUTH2_CLIENT_ID", ""),
        oauth2_client_secret=opts.get("oauth2_client_secret") or os.getenv("OAUTH2_CLIENT_SECRET", ""),
        oauth2_refresh_token=opts.get("oauth2_refresh_token") or os.getenv("OAUTH2_REFRESH_TOKEN", ""),
        bind_host=os.getenv("BIND_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8124")),
    )
