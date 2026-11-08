"""The r07 meta-optimisation knobs (data/r07/knobs.json): the six of the plan
plus ``decomp`` (seed deductive decomposition on/off, added after line A)."""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KNOBS_PATH = ROOT / "data" / "r07" / "knobs.json"

# Candidate values per knob; meta moves one knob to a neighbouring value.
CHOICES: dict[str, list] = {
    "m": [1, 2, 3, 5, 8],
    "k": [0.5, 1.0, 2.0, 3.0, 4.0],
    "max_holes": [0, 1, 2],
    "g4_frac": [0.0, 0.1, 0.2, 0.3, 0.5],
    "order": ["size", "prior"],
    "lam_depth": [1, 2],
    "decomp": [False, True],
}


@dataclass(frozen=True)
class Knobs:
    m: int = 3  # G1 blocks added per pass
    k: float = 2.0  # MDL hole penalty
    max_holes: int = 2  # anti-unification slots
    g4_frac: float = 0.2  # share of the node budget given to G4
    order: str = "prior"  # "size" = size-first only, "prior" = + log-use prior
    lam_depth: int = 2  # lambda body depth (passed to seed when it exposes it)
    decomp: bool = False  # seed deductive decomposition (map/zipwith witness)

    def to_dict(self) -> dict:
        return asdict(self)

    def with_(self, **kw) -> "Knobs":
        return replace(self, **kw)


def load(path: Path = KNOBS_PATH) -> Knobs:
    if not path.exists():
        return Knobs()
    data = json.loads(path.read_text())
    return Knobs(**{k: data[k] for k in Knobs().to_dict() if k in data})


def save(knobs: Knobs, path: Path = KNOBS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(knobs.to_dict(), indent=1, sort_keys=True) + "\n")


def neighbours(knobs: Knobs, name: str) -> list:
    """Values adjacent to the current one in CHOICES (deterministic order)."""
    vals = CHOICES[name]
    cur = getattr(knobs, name)
    if cur not in vals:
        return [v for v in vals if v != cur]
    i = vals.index(cur)
    return [vals[j] for j in (i + 1, i - 1) if 0 <= j < len(vals)]
