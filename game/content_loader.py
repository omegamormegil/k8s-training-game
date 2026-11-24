"""Loads Module/Objective/Task definitions out of the content/*.yaml files."""
import os
from typing import List, Optional

import yaml

from .models import Module, Objective, Task


def load_module(path: str) -> Module:
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    objectives = []
    for obj in data.get("objectives", []):
        tasks = []
        for t in obj.get("tasks", []):
            tasks.append(
                Task(
                    id=t["id"],
                    prompt=t["prompt"].strip(),
                    checks=t.get("checks", []),
                    hints=t.get("hints", []) or [],
                    setup=t.get("setup", []) or [],
                    cleanup=t.get("cleanup", []) or [],
                    points=t.get("points", 1),
                    exam_tip=(t.get("exam_tip") or "").strip(),
                )
            )
        objectives.append(Objective(id=obj["id"], title=obj["title"], tasks=tasks))

    return Module(
        id=data["id"],
        title=data["title"],
        exam=data["exam"],
        weight=data.get("weight", 0),
        objectives=objectives,
    )


def load_all_modules(content_dir: str, exam: Optional[str] = None) -> List[Module]:
    """Walk content_dir for *.yaml files and load them, optionally filtered by exam."""
    modules = []
    for root, _dirs, files in os.walk(content_dir):
        for fname in sorted(files):
            if fname.endswith((".yaml", ".yml")):
                path = os.path.join(root, fname)
                try:
                    module = load_module(path)
                except Exception as e:  # noqa: BLE001 - surfacing bad content files is useful
                    raise RuntimeError(f"Failed to load content file {path}: {e}") from e
                if exam is None or module.exam.lower() == exam.lower():
                    modules.append(module)
    modules.sort(key=lambda m: m.id)
    return modules
