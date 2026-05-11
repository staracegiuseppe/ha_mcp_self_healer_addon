import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from config import Settings
from ha_client import HomeAssistantClient
from loop_detector import detect_loops
from log_analyzer import parse_error_log
from models import ActionResult, HealingAction, HealingReport, LogIssue
from notifier import EmailNotifier
from playbooks import decide_actions

log = logging.getLogger(__name__)
STATE_PATH = Path("/data/self_healer_state.json")
LOCAL_STATE_PATH = Path(".self_healer_state.json")


class SelfHealingAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ha = HomeAssistantClient(settings)
        self.notifier = EmailNotifier(settings)
        self.last_report: HealingReport | None = None
        self._stop = threading.Event()
        state = self._load_state()
        self._seen = set(state.get("seen", []))
        self._history = list(state.get("history", []))[-50:]

    def start_background(self) -> threading.Thread:
        thread = threading.Thread(target=self._loop, name="self-healer-loop", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict[str, Any]:
        return {
            "running": not self._stop.is_set(),
            "dry_run": self.settings.dry_run,
            "auto_fix_enabled": self.settings.auto_fix_enabled,
            "loop_monitor_enabled": self.settings.loop_monitor_enabled,
            "loop_window_minutes": self.settings.loop_window_minutes,
            "loop_toggle_threshold": self.settings.loop_toggle_threshold,
            "loop_automation_threshold": self.settings.loop_automation_threshold,
            "allow_automation_disable": self.settings.allow_automation_disable,
            "ha_url": self.settings.ha_url,
            "supervisor_url": self.settings.supervisor_url,
            "seen_errors": len(self._seen),
            "history_count": len(self._history),
            "last_report": self.last_report.model_dump(mode="json") if self.last_report else None,
        }

    def history(self) -> list[dict[str, Any]]:
        return list(reversed(self._history))

    def check_logs(self) -> list[LogIssue]:
        raw = self.ha.error_log()
        issues = parse_error_log(raw, self.settings.ignored_patterns)
        return [issue for issue in issues if issue.fingerprint not in self._seen]

    def run_once(self, notify: bool = True) -> HealingReport:
        report = HealingReport()
        try:
            issues = self.check_logs()
            report.issues = issues
            for issue in issues:
                for action in decide_actions(issue, self.settings):
                    if len(report.actions) >= self.settings.max_actions_per_cycle:
                        break
                    report.actions.append(self._execute_action(action))
                self._seen.add(issue.fingerprint)

            for issue, actions in self.detect_live_loops():
                if issue.fingerprint in self._seen:
                    continue
                report.issues.append(issue)
                for action in actions:
                    if len(report.actions) >= self.settings.max_actions_per_cycle:
                        break
                    report.actions.append(self._execute_action(action))
                self._seen.add(issue.fingerprint)

            report.summary = self._summary(report)
            report.finished_at = datetime.utcnow()
            self.last_report = report
            self._record_report(report)
            self._save_state()
            if notify and (report.issues or self.settings.notify_on_noop):
                self.notifier.send_report(report)
            return report
        except Exception as exc:
            log.exception("Self healing cycle failed")
            issue = LogIssue(
                fingerprint=f"self-healer-{int(time.time())}",
                severity="critical",
                source="ha_mcp_self_healer.agent",
                message=f"Errore interno agente: {exc}",
            )
            report.issues = [issue]
            report.summary = "Il ciclo di self-healing non e' riuscito a completarsi."
            report.finished_at = datetime.utcnow()
            self.last_report = report
            self._record_report(report)
            self._save_state()
            if notify:
                self.notifier.send_report(report)
            return report

    def detect_live_loops(self) -> list[tuple[LogIssue, list[HealingAction]]]:
        if not self.settings.loop_monitor_enabled:
            return []
        try:
            entries = self.ha.logbook_recent(self.settings.loop_window_minutes)
            return detect_loops(entries, self.settings)
        except Exception as exc:
            log.warning("Loop monitor failed: %s", exc)
            return []

    def _loop(self) -> None:
        log.info("Self-healing loop started, interval=%ss", self.settings.check_interval_seconds)
        while not self._stop.is_set():
            self.run_once(notify=True)
            self._stop.wait(self.settings.check_interval_seconds)

    def _execute_action(self, action: HealingAction) -> ActionResult:
        if not action.allowed:
            return ActionResult(action=action, status="skipped", detail="Azione non consentita dalla configurazione.")
        if not self.settings.auto_fix_enabled:
            return ActionResult(action=action, status="skipped", detail="Auto-fix disabilitato.")
        if self.settings.dry_run:
            return ActionResult(action=action, status="dry_run", detail="Dry-run: azione simulata, nessuna modifica applicata.")

        try:
            if action.kind == "reload_integration":
                response = self.ha.reload_integration(action.payload["entry_id"])
            elif action.kind == "reload_core_config":
                response = self.ha.reload_core_config()
            elif action.kind == "restart_homeassistant":
                backup = None
                if self.settings.create_backup_before_restart:
                    backup = self.ha.create_backup(f"Self Healer backup {datetime.utcnow().isoformat()}Z")
                response = {"backup": backup, "restart": self.ha.restart_homeassistant()}
            elif action.kind == "restart_addon":
                slug = action.payload["slug"]
                response = self.ha.restart_addon(slug)
            elif action.kind == "disable_automation":
                response = self.ha.turn_off_automation(action.payload["entity_id"])
            elif action.kind == "wait_and_recheck":
                time.sleep(int(action.payload.get("seconds", 30)))
                response = {"waited": action.payload.get("seconds", 30)}
            elif action.kind == "notify_only":
                return ActionResult(action=action, status="skipped", detail=action.reason)
            else:
                return ActionResult(action=action, status="skipped", detail=f"Azione sconosciuta: {action.kind}")
            return ActionResult(action=action, status="success", detail="Azione completata.", response=response)
        except Exception as exc:
            return ActionResult(action=action, status="failed", detail=str(exc))

    def _summary(self, report: HealingReport) -> str:
        if not report.issues:
            return "Nessun nuovo errore rilevato nei log Home Assistant."
        successes = sum(1 for action in report.actions if action.status == "success")
        dry_runs = sum(1 for action in report.actions if action.status == "dry_run")
        failed = sum(1 for action in report.actions if action.status == "failed")
        skipped = sum(1 for action in report.actions if action.status == "skipped")
        return (
            f"Rilevati {len(report.issues)} nuovi errore/i. "
            f"Azioni: {successes} completate, {dry_runs} simulate, {failed} fallite, {skipped} saltate."
        )

    def _record_report(self, report: HealingReport) -> None:
        if not report.issues and not report.actions:
            return
        self._history.append(report.model_dump(mode="json"))
        self._history = self._history[-50:]

    def _load_state(self) -> dict[str, Any]:
        path = STATE_PATH if STATE_PATH.parent.exists() else LOCAL_STATE_PATH
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {"seen": data, "history": []}
        except Exception:
            pass
        return {"seen": [], "history": []}

    def _save_state(self) -> None:
        path = STATE_PATH if STATE_PATH.parent.exists() else LOCAL_STATE_PATH
        try:
            path.write_text(
                json.dumps({"seen": sorted(self._seen)[-500:], "history": self._history[-50:]}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            log.warning("Unable to save state", exc_info=True)
