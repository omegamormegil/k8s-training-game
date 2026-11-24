"""Tracks which tasks the learner has completed, persisted as JSON so
progress survives across sessions."""
import json
import os
from datetime import datetime, timezone
from typing import Iterable, Tuple

DEFAULT_PATH = os.path.expanduser("~/.k8s_learning_game/progress.json")


class ProgressTracker:
    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def is_complete(self, task_id: str) -> bool:
        return self.data.get(task_id, {}).get("complete", False)

    def mark_complete(self, task_id: str) -> None:
        self.data[task_id] = {
            "complete": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def reset_task(self, task_id: str) -> None:
        self.data.pop(task_id, None)
        self.save()

    def reset_all(self) -> None:
        self.data = {}
        self.save()

    def stats(self, task_ids: Iterable[str]) -> Tuple[int, int]:
        ids = list(task_ids)
        done = sum(1 for t in ids if self.is_complete(t))
        return done, len(ids)
