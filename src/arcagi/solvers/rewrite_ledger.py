"""Per-task bookkeeping of the rewrite search: which rules tried / hit.

``tried`` counts evaluated candidates per rule, ``hits`` counts train-consistent
programs per rule (a two-edit program credits both of its rules), ``macros``
counts macro names inside hit programs. ``seed_iou`` is the best seed's
foreground IoU; ``gated`` means it fell below ``gate`` and nothing was edited.
``to_json`` goes into the trace metadata (``rewrite``) so a later epoch can pay
out per rule.
"""

from collections import Counter
from dataclasses import dataclass, field

from arcagi.dsl.program import Program

from .rewrite_rules import MACROS


@dataclass
class RewriteLedger:
    tried: Counter[str] = field(default_factory=Counter)
    hits: Counter[str] = field(default_factory=Counter)
    macros: Counter[str] = field(default_factory=Counter)
    candidates: int = 0
    seconds: float = 0.0
    out_of_budget: bool = False
    solved: bool = False
    gate: float = 0.0
    seed_iou: float | None = None
    gated: bool = False

    def try_(self, rules: tuple[str, ...]) -> None:
        self.candidates += 1
        self.tried[rules[-1]] += 1

    def hit(self, rules: tuple[str, ...], program: Program) -> None:
        for rule in rules:
            self.hits[rule] += 1
        for step in program:
            if step[0] in MACROS:
                self.macros[str(step[0])] += 1

    def to_json(self) -> dict[str, object]:
        return {
            "hits": dict(self.hits),
            "tried": dict(self.tried),
            "macros": dict(self.macros),
            "candidates": self.candidates,
            "seconds": round(self.seconds, 3),
            "out_of_budget": self.out_of_budget,
            "solved": self.solved,
            "gate": self.gate,
            "seed_iou": None if self.seed_iou is None else round(self.seed_iou, 4),
            "gated": self.gated,
        }


__all__ = ["RewriteLedger"]
