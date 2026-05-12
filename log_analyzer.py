import hashlib
import re

from models import LogIssue


ANSI = re.compile(r"\x1b\[[0-9;]*m")
LOG_LINE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) (?P<level>[A-Z]+) \((?P<thread>[^)]+)\) \[(?P<source>[^\]]+)\] (?P<message>.*)$")
ERROR_START = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) (?P<level>ERROR|WARNING|CRITICAL) \((?P<thread>[^)]+)\) \[(?P<source>[^\]]+)\] (?P<message>.*)$")
HOST_LINE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) (?P<host>\S+) (?P<process>[a-zA-Z0-9_.-]+)(?:\[\d+\])?: (?P<message>.*)$")
DOCKER_LEVEL = re.compile(r'level=(?P<level>error|warning|warn|fatal|critical)\s+msg="(?P<message>[^"]+)"(?P<tail>.*)$', re.IGNORECASE)
TRACEBACK_STARTS = (
    "Traceback (most recent call last):",
    "During handling of the above exception, another exception occurred:",
)


def _fingerprint(source: str, message: str) -> str:
    normalized = re.sub(r"0x[0-9a-fA-F]+|\d{4,}", "#", f"{source}:{message}")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def parse_error_log(raw_log: str, ignored_patterns: list[str] | None = None, limit: int = 50) -> list[LogIssue]:
    ignored_patterns = ignored_patterns or []
    issues: list[LogIssue] = []
    current: dict[str, str] | None = None
    traceback_lines: list[str] = []
    orphan_traceback: list[str] = []

    for raw_line in raw_log.splitlines():
        line = ANSI.sub("", raw_line)
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
        host_match = HOST_LINE.match(line)
        if host_match:
            host_issue = _host_issue_fields(host_match)
            if host_issue:
                if current:
                    issues.append(_build_issue(current, traceback_lines))
                    traceback_lines = []
                elif orphan_traceback:
                    issues.append(_build_orphan_traceback(orphan_traceback))
                    orphan_traceback = []
                current = host_issue
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


def _host_issue_fields(match: re.Match[str]) -> dict[str, str] | None:
    process = match.group("process")
    message = match.group("message")
    docker = DOCKER_LEVEL.search(message)
    if docker:
        level = docker.group("level").upper().replace("WARN", "WARNING")
        detail = docker.group("message")
        tail = docker.group("tail").strip()
        if tail:
            detail = f"{detail} {tail}"
        return {
            "date": match.group("date"),
            "level": level,
            "thread": process,
            "source": f"host.{process}",
            "message": detail,
        }
    lowered = message.lower()
    if "error reading preface" in lowered or "connection reset by peer" in lowered:
        return {
            "date": match.group("date"),
            "level": "WARNING",
            "thread": process,
            "source": f"host.{process}",
            "message": message,
        }
    return None


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
