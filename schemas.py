from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

IntentLiteral = Literal["summarize", "create_tasks", "needs_clarification", "unsupported"]
TraceStatusLiteral = Literal["success", "warning", "error"]


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, description="Raw user input or pasted note text.")
    source_name: str | None = Field(default=None, max_length=200)


class TaskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., min_length=3, max_length=240)
    deadline: str | None = Field(default=None, max_length=120)
    source_excerpt: str | None = Field(default=None, max_length=240)


class ConfirmationGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool
    reason: str
    message: str


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    schema_name: str = "AssistResponse"
    errors: list[str] = Field(default_factory=list)


class TraceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    trace_id: str
    stage: str
    status: TraceStatusLiteral
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = Field(default_factory=dict)


class AssistResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    trace_id: str
    intent: IntentLiteral
    confidence: float = Field(..., ge=0.0, le=1.0)
    message: str
    summary: str | None = None
    tasks: list[TaskItem] = Field(default_factory=list)
    confirmation_gate: ConfirmationGate | None = None
    validation: ValidationResult
    trace: list[TraceEntry] = Field(default_factory=list)
