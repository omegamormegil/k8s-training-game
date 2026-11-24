"""Data models for the K8s Learning Game content tree.

Hierarchy:  Module (an exam domain, e.g. "Workloads & Scheduling")
              -> Objective (a specific exam objective within that domain)
                   -> Task (one concrete, checkable exercise)
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Task:
    id: str
    prompt: str
    checks: List[Dict[str, Any]] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    setup: List[str] = field(default_factory=list)      # shell commands run once when task is opened
    cleanup: List[str] = field(default_factory=list)    # shell commands run when task is reset
    points: int = 1
    exam_tip: str = ""

    @property
    def is_manual(self) -> bool:
        return any(c.get("type") == "manual" for c in self.checks)


@dataclass
class Objective:
    id: str
    title: str
    tasks: List[Task] = field(default_factory=list)


@dataclass
class Module:
    id: str
    title: str
    exam: str          # "CKA" or "CKAD"
    weight: int         # percentage weight in the real exam, for context
    objectives: List[Objective] = field(default_factory=list)

    def all_tasks(self) -> List[Task]:
        return [t for o in self.objectives for t in o.tasks]
