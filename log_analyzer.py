import hashlib
import re

from models import LogIssue


ERROR_START = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) (?P<level>ERROR|WARNING|CRITICAL) \((?P<thread>[^)]+)\) \[(?P<source>[^\]]+)\] (?P<message>.*)$")


def _fingerprint(source: str, message: str) -> str:
    normalized = re.sub(r"0x[0-9a-fA-F]+|\d{4,}", "#", f"{source}:{message}")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def parse_error_log(raw_log: str, ignored_patterns: list[str] | None = None, limit: int = 20) -> list[LogIssue]:
    ignored_patterns = ignored_patterns or []
    issues: list[LogIssue] = []
    current: dict[str, str] | None = None
    traceback_lines: list[str] = []

    for line in raw_log.splitlines():
        match = ERROR_START.match(line)
        if match:
            if current:
                issues.append(_build_issue(current, traceback_lines))
            current = match.groupdict()
            traceback_lines = []
            continue
        if current:
            traceback_lines.append(line)

    if current:
        issues.append(_build_issue(current, traceback_lines))

    filtered = []
    seen = set()
    for issue in reversed(issues):
        text = f"{issue.source}\n{issue.message}\n{issue.traceback}"
        if any(pattern and pattern.lower() in text.lower() for pattern in ignored_patterns):
            continue
        if issue.fingerprint in seen:
            continue
        seen.add(issue.fingerprint)
        filtered.append(issue)
        if len(filtered) >= limit:
            break
    return filtered


def _build_issue(fields: dict[str, str], traceback_lines: list[str]) -> LogIssue:
    level = fields.get("level", "ERROR").lower()
    severity = "critical" if level == "critical" else "warning" if level == "warning" else "error"
    source = fields.get("source", "unknown")
    message = fields.get("message", "").strip()
    traceback = "\n".join(traceback_lines).strip()[-5000:]
    return LogIssue(
        fingerprint=_fingerprint(source, message),
        severity=severity,
        source=source,
        message=message,
        traceback=traceback,
    )
