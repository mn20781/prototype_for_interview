from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from pydantic import ValidationError

from logging_utils import TraceLogger
from schemas import AssistResponse, ConfirmationGate, TaskItem, ValidationResult

TASK_HINTS = (
    "task",
    "tasks",
    "action item",
    "action items",
    "actionable",
    "deadline",
    "deadlines",
    "follow up",
    "follow-up",
    "next steps",
)
SUMMARY_HINTS = (
    "summarize",
    "summary",
    "key points",
    "takeaways",
    "main points",
    "tldr",
)
ACTION_PATTERNS = (
    "need to",
    "needs to",
    "should",
    "must",
    "follow up",
    "review",
    "schedule",
    "draft",
    "finalize",
    "prepare",
    "send",
    "confirm",
    "deliver",
    "share",
    "update",
)
DEADLINE_PATTERN = re.compile(
    r"\b("
    r"\d{4}-\d{2}-\d{2}"
    r"|today"
    r"|tomorrow"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|next week"
    r"|eod"
    r"|end of day"
    r"|q[1-4]"
    r"|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
    r"|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")(?:\s+\d{1,2}(?:,\s*\d{4})?)?\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(slots=True)
class IntentDecision:
    intent: str
    confidence: float
    reason: str
    task_score: int
    summary_score: int


def _normalize_text(raw_text: str) -> str:
    return re.sub(r"\s+", " ", raw_text).strip()


def _split_sentences(raw_text: str) -> list[str]:
    return [part.strip(" -") for part in SENTENCE_SPLIT_PATTERN.split(raw_text) if part.strip()]


def classify_intent(raw_text: str) -> IntentDecision:
    normalized = _normalize_text(raw_text)
    lowered = normalized.lower()
    task_score = sum(1 for hint in TASK_HINTS if hint in lowered)
    summary_score = sum(1 for hint in SUMMARY_HINTS if hint in lowered)

    if len(normalized) < 25:
        return IntentDecision(
            intent="needs_clarification",
            confidence=0.32,
            reason="input_too_short_for_reliable_classification",
            task_score=task_score,
            summary_score=summary_score,
        )
    if task_score and summary_score:
        return IntentDecision(
            intent="create_tasks",
            confidence=0.86,
            reason="compound_request_prioritized_to_task_generation",
            task_score=task_score,
            summary_score=summary_score,
        )
    if task_score:
        return IntentDecision(
            intent="create_tasks",
            confidence=0.82,
            reason="task_or_action_language_detected",
            task_score=task_score,
            summary_score=summary_score,
        )
    if summary_score:
        return IntentDecision(
            intent="summarize",
            confidence=0.88,
            reason="summary_language_detected",
            task_score=task_score,
            summary_score=summary_score,
        )

    looks_like_note = len(normalized) > 80 and len(_split_sentences(normalized)) >= 2
    if looks_like_note:
        return IntentDecision(
            intent="needs_clarification",
            confidence=0.41,
            reason="note_present_but_request_is_ambiguous",
            task_score=task_score,
            summary_score=summary_score,
        )
    return IntentDecision(
        intent="unsupported",
        confidence=0.22,
        reason="no_supported_operation_detected",
        task_score=task_score,
        summary_score=summary_score,
    )


def extract_tasks(raw_text: str) -> tuple[list[TaskItem], list[str], bool]:
    sentences = _split_sentences(raw_text)
    candidate_lines: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(pattern in lowered for pattern in ACTION_PATTERNS) or DEADLINE_PATTERN.search(sentence):
            candidate_lines.append(sentence)

    if not candidate_lines:
        candidate_lines = sentences[:3]

    tasks: list[TaskItem] = []
    key_points: list[str] = []
    missing_deadline = False

    for sentence in candidate_lines:
        clean_sentence = re.sub(r"^user request:\s*", "", sentence, flags=re.IGNORECASE).strip()
        clean_sentence = re.sub(r"^source:\s*", "", clean_sentence, flags=re.IGNORECASE).strip()
        if len(clean_sentence) < 8:
            continue

        deadline_match = DEADLINE_PATTERN.search(clean_sentence)
        deadline = deadline_match.group(0) if deadline_match else None
        if deadline is None:
            missing_deadline = True

        description = clean_sentence
        description = re.sub(r"\s+", " ", description).strip()
        description = description.rstrip(".")
        description = description[:1].upper() + description[1:] if description else description

        tasks.append(
            TaskItem(
                description=description[:240],
                deadline=deadline,
                source_excerpt=clean_sentence[:240],
            )
        )
        key_points.append(clean_sentence[:160])
        if len(tasks) >= 3:
            break

    return tasks, key_points, missing_deadline


def build_summary(raw_text: str) -> str:
    sentences = _split_sentences(raw_text)
    meaningful = [sentence for sentence in sentences if len(sentence) > 25]
    if not meaningful:
        return "I could not extract enough substance to produce a reliable summary."
    selected = meaningful[:3]
    return " ".join(selected)


def _clarification_gate(reason: str, message: str) -> ConfirmationGate:
    return ConfirmationGate(required=True, reason=reason, message=message)


def process_assist_request(raw_text: str, source_name: str | None = None) -> AssistResponse:
    request_id = f"req_{uuid4().hex[:12]}"
    trace_id = f"trace_{uuid4().hex[:12]}"
    trace = TraceLogger(request_id=request_id, trace_id=trace_id)
    normalized_text = raw_text.strip()

    trace.log(
        "request_received",
        {
            "raw_input": normalized_text,
            "source_name": source_name,
            "character_count": len(normalized_text),
        },
    )

    decision = classify_intent(normalized_text)
    trace.log(
        "intent_detected",
        {
            "detected_intent": decision.intent,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "task_score": decision.task_score,
            "summary_score": decision.summary_score,
        },
        status="warning" if decision.confidence < 0.6 else "success",
    )

    response_payload: dict[str, object]
    final_status = "success"

    if decision.intent == "create_tasks":
        tasks, key_points, missing_deadline = extract_tasks(normalized_text)
        confirmation_gate = None
        confidence = decision.confidence
        if missing_deadline:
            confidence = min(confidence, 0.74)
            confirmation_gate = _clarification_gate(
                reason="missing_deadline",
                message="At least one extracted task has no explicit deadline. Please confirm dates before using these tasks operationally.",
            )
            final_status = "warning"
        trace.log(
            "task_extraction",
            {
                "task_count": len(tasks),
                "missing_deadline": missing_deadline,
                "key_points": key_points,
            },
            status="warning" if missing_deadline else "success",
        )
        response_payload = {
            "request_id": request_id,
            "trace_id": trace_id,
            "intent": "create_tasks",
            "confidence": confidence,
            "message": "Extracted the most actionable follow-ups from the provided note.",
            "summary": None,
            "tasks": [task.model_dump() for task in tasks],
            "confirmation_gate": confirmation_gate.model_dump() if confirmation_gate else None,
            "validation": {"passed": True, "schema_name": "AssistResponse", "errors": []},
            "trace": [],
        }
    elif decision.intent == "summarize":
        summary = build_summary(normalized_text)
        trace.log(
            "summary_generation",
            {"summary_preview": summary[:220]},
        )
        response_payload = {
            "request_id": request_id,
            "trace_id": trace_id,
            "intent": "summarize",
            "confidence": decision.confidence,
            "message": "Prepared a concise summary of the provided text.",
            "summary": summary,
            "tasks": [],
            "confirmation_gate": None,
            "validation": {"passed": True, "schema_name": "AssistResponse", "errors": []},
            "trace": [],
        }
    elif decision.intent == "needs_clarification":
        final_status = "warning"
        response_payload = {
            "request_id": request_id,
            "trace_id": trace_id,
            "intent": "needs_clarification",
            "confidence": decision.confidence,
            "message": "I need a clearer instruction before I can safely summarize or create tasks from this text.",
            "summary": None,
            "tasks": [],
            "confirmation_gate": _clarification_gate(
                reason=decision.reason,
                message="Please say whether you want a summary or action items, or provide more text if the note is incomplete.",
            ).model_dump(),
            "validation": {"passed": True, "schema_name": "AssistResponse", "errors": []},
            "trace": [],
        }
    else:
        final_status = "warning"
        response_payload = {
            "request_id": request_id,
            "trace_id": trace_id,
            "intent": "unsupported",
            "confidence": decision.confidence,
            "message": "This prototype only supports summarizing notes or turning them into tasks.",
            "summary": None,
            "tasks": [],
            "confirmation_gate": _clarification_gate(
                reason=decision.reason,
                message="Try asking for a summary or for 3 actionable tasks with any deadlines mentioned.",
            ).model_dump(),
            "validation": {"passed": True, "schema_name": "AssistResponse", "errors": []},
            "trace": [],
        }

    try:
        validated_response = AssistResponse.model_validate(response_payload)
        validation = ValidationResult(passed=True, schema_name="AssistResponse", errors=[])
        trace.log("validation_result", validation.model_dump(), status="success")
    except ValidationError as exc:
        errors = [error["msg"] for error in exc.errors()]
        validation = ValidationResult(passed=False, schema_name="AssistResponse", errors=errors)
        trace.log("validation_result", validation.model_dump(), status="error")
        final_status = "error"
        validated_response = AssistResponse(
            request_id=request_id,
            trace_id=trace_id,
            intent="unsupported",
            confidence=0.0,
            message="Response generation failed validation and was downgraded to a safe fallback.",
            summary=None,
            tasks=[],
            confirmation_gate=_clarification_gate(
                reason="validation_error",
                message="The prototype hit a validation issue. Please retry with a simpler note.",
            ),
            validation=validation,
            trace=[],
        )

    trace.log(
        "final_response",
        {
            "intent": validated_response.intent,
            "confidence": validated_response.confidence,
            "task_count": len(validated_response.tasks),
            "confirmation_required": bool(
                validated_response.confirmation_gate and validated_response.confirmation_gate.required
            ),
        },
        status=final_status,
    )

    return validated_response.model_copy(update={"trace": trace.entries, "validation": validation})
