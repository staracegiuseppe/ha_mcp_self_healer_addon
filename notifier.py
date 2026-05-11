import base64
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import Settings
from models import HealingReport

log = logging.getLogger(__name__)
_TOKEN_CACHE = {"access_token": None, "expires_at": 0.0}


class EmailNotifier:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send_report(self, report: HealingReport) -> bool:
        if not self.settings.email_enabled:
            return False
        sender = self.settings.email_from or self.settings.smtp_user or self.settings.email_to
        recipient = self.settings.email_to
        if not sender or not recipient:
            log.error("[EMAIL] sender/recipient mancanti")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[HA Self Healer] {len(report.issues)} errore/i, {len(report.actions)} azione/i"
        msg["From"] = sender
        msg["To"] = recipient
        html = self._html(report)
        text = self._text(report)
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        if self._oauth2_configured(sender):
            if self._send_oauth2(msg, sender, recipient):
                log.info("[EMAIL] invio riuscito via OAuth2")
                return True
            log.warning("[EMAIL] OAuth2 fallito, provo fallback SMTP/App Password")

        if not self.settings.smtp_user or not self.settings.smtp_password:
            log.warning("[EMAIL] fallback SMTP non configurato")
            return False

        ok = self._send_apppassword(msg, sender, recipient)
        if ok:
            log.info("[EMAIL] invio riuscito via SMTP/App Password")
        return ok

    def _oauth2_configured(self, sender: str) -> bool:
        return bool(
            sender.endswith("@gmail.com")
            and self.settings.oauth2_client_id
            and self.settings.oauth2_client_secret
            and self.settings.oauth2_refresh_token
        )

    def _access_token(self) -> str | None:
        if _TOKEN_CACHE["access_token"] and _TOKEN_CACHE["expires_at"] > time.time() + 60:
            return str(_TOKEN_CACHE["access_token"])
        try:
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.settings.oauth2_client_id,
                    "client_secret": self.settings.oauth2_client_secret,
                    "refresh_token": self.settings.oauth2_refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=10,
            )
            if response.status_code != 200:
                log.error("[OAUTH2] token error %s: %s", response.status_code, response.text[:300])
                return None
            data = response.json()
            _TOKEN_CACHE["access_token"] = data["access_token"]
            _TOKEN_CACHE["expires_at"] = time.time() + int(data.get("expires_in", 3600))
            return str(_TOKEN_CACHE["access_token"])
        except Exception as exc:
            log.error("[OAUTH2] token exception: %s", exc)
            return None

    def _send_oauth2(self, msg: MIMEMultipart, sender: str, recipient: str) -> bool:
        token = self._access_token()
        if not token:
            return False
        auth = base64.b64encode(f"user={sender}\x01auth=Bearer {token}\x01\x01".encode()).decode()
        try:
            smtp = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            code, _ = smtp.docmd("AUTH", "XOAUTH2 " + auth)
            if code == 334:
                smtp.docmd("")
            smtp.sendmail(sender, [recipient], msg.as_string())
            smtp.quit()
            return True
        except Exception as exc:
            log.error("[OAUTH2] send failed: %s", exc)
            return False

    def _send_apppassword(self, msg: MIMEMultipart, sender: str, recipient: str) -> bool:
        smtp = None
        try:
            if self.settings.smtp_tls:
                smtp = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20)
                smtp.ehlo()
                smtp.starttls()
            else:
                smtp = smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port, timeout=20)
            smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.sendmail(sender, [recipient], msg.as_string())
            return True
        except smtplib.SMTPAuthenticationError:
            log.error("[SMTP] autenticazione fallita")
            return False
        except Exception as exc:
            log.error("[SMTP] send failed: %s", exc)
            return False
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except Exception:
                    pass

    def _text(self, report: HealingReport) -> str:
        lines = [report.summary, ""]
        for issue in report.issues:
            lines.append(f"- {issue.severity.upper()} {issue.source}: {issue.message}")
        lines.append("")
        for result in report.actions:
            lines.append(f"- {result.status.upper()} {result.action.title}: {result.detail or result.action.reason}")
        return "\n".join(lines)

    def _html(self, report: HealingReport) -> str:
        issues = "".join(
            f"<li><b>{issue.severity.upper()}</b> <code>{issue.source}</code><br>{_esc(issue.message)}</li>"
            for issue in report.issues
        )
        actions = "".join(
            f"<li><b>{result.status.upper()}</b> {result.action.title}<br><small>{_esc(result.detail or result.action.reason)}</small></li>"
            for result in report.actions
        )
        return f"""
        <html>
          <body style="font-family:Arial,sans-serif;color:#172033">
            <h2>Home Assistant MCP Self Healer</h2>
            <p>{_esc(report.summary)}</p>
            <h3>Errori rilevati</h3>
            <ul>{issues or "<li>Nessun errore nuovo.</li>"}</ul>
            <h3>Azioni</h3>
            <ul>{actions or "<li>Nessuna azione eseguita.</li>"}</ul>
          </body>
        </html>
        """


def _esc(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
