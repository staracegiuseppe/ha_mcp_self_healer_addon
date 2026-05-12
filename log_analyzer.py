import hashlib
import re

from models import LogIssue


LOG_LINE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) (?P<level>[A-Z]+) \((?P<thread>[^)]+)\) \[(?P<source>[^\]]+)\] (?P<message>.*)$")
ERROR_START = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) (?P<level>ERROR|WARNING|CRITICAL) \((?P<thread>[^)]+)\) \[(?P<source>[^\]]+)\] (?P<message>.*)$")
TRACEBACK_STARTS = (
    "Traceback (most recent call last):",
    "During handling of the above exception, another exception occurred:",
)


def _fingerprint(source: str, message: str) -> str:
    normalized = re.sub(r"0x[0-9a-fA-F]+|\d{4,}", "#", f"{source}:{message}")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def parse_error_log(raw_log: str, ignored_patterns: list[str] | None = None, limit: int = 20) -> list[LogIssue]:
    ignored_patterns = ignored_patterns or []
    issues: list[LogIssue] = []
    current: dict[str, str] | None = None
    traceback_lines: list[str] = []
    orphan_traceback: list[str] = []

    for line in raw_log.splitlines():
        match = ERROR_START.match(line)
        if match:
            if current:
                issues.append(_build_issue(current, traceback_lines))
            elif orphan_traceback:
                issues.append(_build_orphan_traceback(orphan_traceback))
                orphan_traceback = []
            current = match.groupdict()
            traceback_lines = []
            continue
        if LOG_LINE.match(line):
            if current:
                issues.append(_build_issue(current, traceback_lines))
                current = None
                traceback_lines = []
            elif orphan_traceback:
                issues.append(_build_orphan_traceback(orphan_traceback))
                orphan_traceback = []
            continue
        if current:
            if not _is_debug_noise(line):
                traceback_lines.append(line)
            continue
        if orphan_traceback or line.startswith(TRACEBACK_STARTS) or line.startswith("  File "):
            if not _is_debug_noise(line):
                orphan_traceback.append(line)

    if current:
        issues.append(_build_issue(current, traceback_lines))
    elif orphan_traceback:
        issues.append(_build_orphan_traceback(orphan_traceback))

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


def _is_debug_noise(line: str) -> bool:
    match = LOG_LINE.match(line)
    return bool(match and match.group("level") == "DEBUG")


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


def _build_orphan_traceback(traceback_lines: list[str]) -> LogIssue:
    traceback = "\n".join(traceback_lines).strip()[-5000:]
    exception = "Traceback orfano"
    for line in reversed(traceback_lines):
        stripped = line.strip()
        if re.match(r"^[a-zA-Z_][\w.]*Error:", stripped) or "Exception:" in stripped:
            exception = stripped
            break
    return LogIssue(
        fingerprint=_fingerprint("homeassistant.orphan_traceback", exception),
        severity="error",
        source="homeassistant.orphan_traceback",
        message=exception,
        traceback=traceback,
    )
