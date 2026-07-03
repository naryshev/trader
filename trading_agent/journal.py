"""Audit trail: a JSONL journal of every tool call plus a markdown report per run."""

import json
from datetime import datetime, timezone
from pathlib import Path


class Journal:
    def __init__(self, journal_dir: Path):
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        journal_dir.mkdir(parents=True, exist_ok=True)
        (journal_dir / "reports").mkdir(exist_ok=True)
        self._events_path = journal_dir / f"run-{self.run_id}.jsonl"
        self._report_path = journal_dir / "reports" / f"report-{self.run_id}.md"

    def record(self, kind: str, payload: dict) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            **payload,
        }
        with self._events_path.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def write_report(self, text: str) -> Path:
        self._report_path.write_text(text)
        return self._report_path

    def make_audit_hooks(self):
        """PreToolUse/PostToolUse hooks that journal every tool call."""

        async def log_pre(input_data, tool_use_id, context):
            self.record(
                "tool_call",
                {
                    "tool_use_id": tool_use_id,
                    "tool_name": input_data.get("tool_name"),
                    "tool_input": input_data.get("tool_input"),
                },
            )
            return {}

        async def log_post(input_data, tool_use_id, context):
            response = input_data.get("tool_response")
            self.record(
                "tool_result",
                {
                    "tool_use_id": tool_use_id,
                    "tool_name": input_data.get("tool_name"),
                    # Truncate large payloads; the full data lived in the session.
                    "tool_response": str(response)[:4000],
                },
            )
            return {}

        return log_pre, log_post
