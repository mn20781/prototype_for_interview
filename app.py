from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from pipeline import process_assist_request
from schemas import AssistRequest, AssistResponse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"

app = FastAPI(title="Sentinel Mini Interview Prototype")


@app.get("/", response_class=FileResponse)
def serve_index() -> FileResponse:
    return FileResponse(INDEX_HTML)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/assist/process", response_model=AssistResponse)
def process_note(payload: AssistRequest) -> AssistResponse:
    return process_assist_request(payload.text, source_name=payload.source_name)
