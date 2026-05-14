from __future__ import annotations

from dataclasses import dataclass, field

from schemas import TraceEntry


@dataclass(slots=True)
class TraceLogger:
    request_id: str
    trace_id: str
    entries: list[TraceEntry] = field(default_factory=list)

    def log(self, stage: str, payload: dict, status: str = "success") -> None:
        self.entries.append(
            TraceEntry(
                request_id=self.request_id,
                trace_id=self.trace_id,
                stage=stage,
                status=status,
                payload=payload,
            )
        )
