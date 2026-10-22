"""证据流：ORA 式全链路落盘——planner 咨询、原语裁决、执行回执、verifier 判定。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from .types import EvidenceRecord


class Evidence:
    def __init__(self, log_dir: str | Path = "evidence") -> None:
        self.records: list[EvidenceRecord] = []
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / f"evidence-{int(time.time())}.jsonl"

    def log(self, kind: str, payload: dict) -> None:
        rec = EvidenceRecord(kind=kind, payload=payload)
        self.records.append(rec)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    def summary(self) -> dict:
        kinds = [r.kind for r in self.records]
        return {
            "total": len(kinds),
            "vetoes": kinds.count("veto"),
            "executes": kinds.count("execute"),
            "verifies": kinds.count("verify"),
            "path": str(self.path),
        }
