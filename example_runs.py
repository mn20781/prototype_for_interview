from __future__ import annotations

from pipeline import process_assist_request

EXAMPLES = [
    (
        "happy_path_tasks",
        "Find the key points in this research note and turn them into 3 actionable tasks with deadlines if mentioned. "
        "We need to finalize the ad copy by Friday. John should schedule the vendor call on 2026-05-20. "
        "Also draft the follow-up email for the launch team.",
    ),
    (
        "edge_case_missing_deadline",
        "Create tasks from this email. Review the customer objections with legal. Draft a concise reply to finance. "
        "Confirm the launch checklist by 2026-05-30.",
    ),
    (
        "failure_case_short_input",
        "Help?",
    ),
]


def main() -> None:
    for name, text in EXAMPLES:
        print(f"\n=== {name} ===")
        response = process_assist_request(text)
        print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
