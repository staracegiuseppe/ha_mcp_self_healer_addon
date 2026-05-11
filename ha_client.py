import logging
from typing import Any

import requests

from config import Settings

log = logging.getLogger(__name__)


class HomeAssistantClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.ha_url.rstrip("/")
        self.supervisor_url = settings.supervisor_url.rstrip("/")
        self.session = requests.Session()
        self.supervisor_session = requests.Session()
        if settings.ha_token:
            self.session.headers.update({"Authorization": f"Bearer {settings.ha_token}"})
        supervisor_token = settings.supervisor_token or settings.ha_token
        if supervisor_token:
            self.supervisor_session.headers.update({"Authorization": f"Bearer {supervisor_token}"})
        self.session.headers.update({"Content-Type": "application/json"})
        self.supervisor_session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _supervisor_api_url(self, path: str, base_url: str | None = None) -> str:
        return f"{(base_url or self.supervisor_url).rstrip('/')}/{path.lstrip('/')}"

    def get(self, path: str, timeout: int = 20) -> Any:
        response = self.session.get(self._url(path), timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    def supervisor_get(self, path: str, timeout: int = 20, base_url: str | None = None) -> Any:
        response = self.supervisor_session.get(self._supervisor_api_url(path, base_url), timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    def post(self, path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> Any:
        response = self.session.post(self._url(path), json=payload or {}, timeout=timeout)
        response.raise_for_status()
        if not response.text:
            return {"ok": True}
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return {"ok": True, "text": response.text[:500]}

    def health(self) -> dict[str, Any]:
        config = self.get("/api/config")
        return {"connected": True, "location": config.get("location_name"), "version": config.get("version")}

    def error_log(self) -> str:
        try:
            return str(self.get("/api/error_log", timeout=30))
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status != 404:
                raise
            log.info("/api/error_log returned 404, falling back to Supervisor logs")
            return self._supervisor_logs_with_fallback()

    def _supervisor_logs_with_fallback(self) -> str:
        candidates = []
        for base_url in (self.supervisor_url, "http://supervisor"):
            if base_url and base_url not in candidates:
                candidates.append(base_url)

        errors = []
        for base_url in candidates:
            for path in ("/core/logs", "/host/logs"):
                try:
                    return str(self.supervisor_get(path, timeout=30, base_url=base_url))
                except requests.HTTPError as exc:
                    status = exc.response.status_code if exc.response is not None else "unknown"
                    errors.append(f"{base_url}{path}: HTTP {status}")
                except Exception as exc:
                    errors.append(f"{base_url}{path}: {exc}")

        message = "Log Home Assistant non disponibili via REST o Supervisor. " + "; ".join(errors)
        log.warning(message)
        return (
            "2026-01-01 00:00:00.000 WARNING (MainThread) "
            f"[ha_mcp_self_healer.logs] {message}"
        )

    def call_service(self, domain: str, service: str, data: dict[str, Any] | None = None) -> Any:
        return self.post(f"/api/services/{domain}/{service}", data or {})

    def reload_integration(self, entry_id: str) -> Any:
        return self.post("/api/services/homeassistant/reload_config_entry", {"entry_id": entry_id})

    def restart_homeassistant(self) -> Any:
        return self.call_service("homeassistant", "restart", {})

    def reload_core_config(self) -> Any:
        return self.call_service("homeassistant", "reload_core_config", {})

    def create_backup(self, name: str) -> Any:
        try:
            return self.call_service("hassio", "backup_partial", {
                "name": name,
                "homeassistant": True,
                "addons": [],
                "folders": [],
                "homeassistant_exclude_database": True,
            })
        except Exception as exc:
            log.warning("Backup via Supervisor API failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def restart_addon(self, slug: str) -> Any:
        return self.call_service("hassio", "addon_restart", {"addon": slug})
