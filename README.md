# Sentinel Mini Interview Prototype

Small working prototype inspired by a practical assistant flow: accept a text note, classify the request into a fixed intent set, and return validated structured output with trace logging and a confirmation gate when confidence is low.

## What I built in 30-45 minutes

- A tiny FastAPI endpoint at `POST /api/assist/process`
- A single-page HTML frontend served by the backend
- Fixed intent classification: `summarize`, `create_tasks`, `needs_clarification`, `unsupported`
- Pydantic-backed request/response validation
- Lightweight trace logging for:
  - request received
  - detected intent
  - extraction/summary stage
  - validation result
  - final response
- A confirmation gate when extracted tasks are missing explicit deadlines
- Client-side retry logic with one automatic retry for network or `5xx` failures
- `unittest` coverage plus runnable example responses

## Setup and run

```bash
cd interview_prototype
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8005
```

Then open [http://127.0.0.1:8005](http://127.0.0.1:8005).

## Run tests

```bash
cd interview_prototype
python3 -m unittest tests/test_app.py
```

## Run example outputs

```bash
cd interview_prototype
python3 example_runs.py
```

## What the prototype does

- Accepts plain text input from a pasted note, email snippet, or attached text file
- Uses lightweight heuristics to classify the request
- Produces structured validated JSON
- Surfaces ambiguity instead of guessing when the input is too short or deadlines are missing
- Shows both frontend retry events and backend trace events in the sidebar

## What I intentionally skipped

- No OCR, PDF parsing, or Gmail integration
- No database or persistence layer
- No authentication or user accounts
- No LLM dependency; I kept the logic deterministic so it is easier to explain and test
- No planner sync or downstream action execution

## AI tools used

- OpenAI Codex / GPT-5 coding assistant for implementation, iteration, and review

## Tradeoffs and debugging decisions

- I used deterministic heuristics instead of an LLM because the brief emphasized judgment and reliability over breadth.
- I kept the frontend as a single HTML file so the ZIP stays easy to inspect and easy to run locally.
- I added one retry only, rather than a more complex retry policy, because anything more would add noise without improving the demo much.
- I chose to return a confirmation gate for missing deadlines instead of inventing dates, because guessing would look less reliable in an interview.
- I kept the response schema intentionally small and explicit so validation errors are easy to reason about.

## Example requests

### Happy path

```text
Find the key points in this research note and turn them into 3 actionable tasks with deadlines if mentioned. We need to finalize the ad copy by Friday. John should schedule the vendor call on 2026-05-20. Also draft the follow-up email for the launch team.
```

### Confirmation gate

```text
Create tasks from this email. Review the customer objections with legal. Draft a concise reply to finance. Confirm the launch checklist by 2026-05-30.
```

### Needs clarification

```text
Help?
```

## Render note

This is deployable as a simple Python web service. The start command is:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```
