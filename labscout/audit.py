"""
audit.py — Append-only action logging.

Every action LabScout takes (and every one it refuses) is written here as a
timestamped JSON line. This gives you a reviewable record of exactly what was
run against the lab, which is a core requirement for authorized testing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    def __init__(self, path: str | Path = "labscout_audit.log",
                 session: str | None = None):
        self.path = Path(path)
        # An optional session id ties all the lines from one run together, so a
        # later reviewer can see exactly which actions belonged to which run.
        self.session = session

    def record(self, event: str, **fields) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
        }
        if self.session:
            entry["session"] = self.session
        entry.update(fields)
        line = json.dumps(entry, default=str)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
