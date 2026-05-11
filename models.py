from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LogIssue(BaseModel):
    fingerprint: str
    severity: Literal["warning", "error", "critical"]
    source: str
    message: str
    traceback: str = ""
    first_seen: datetime = Field(default_factory=datetime.utcnow)


class HealingAction(BaseModel):
    kind: str
    title: str
    reason: str
    allowed: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    action: HealingAction
    status: Literal["skipped", "dry_run", "success", "failed"]
    detail: str = ""
    response: Any = None


class HealingReport(BaseModel):
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    issues: list[LogIssue] = Field(default_factory=list)
    actions: list[ActionResult] = Field(default_factory=list)
    summary: str = ""
