"""Seeded (mu + lambda) survival with two elites and tournament size three."""

import random
import shutil
from pathlib import Path

from arcagi.hammer.formats import write_json

from . import boundary


def select(candidates: list[dict], out: Path, hall: Path, *, seed: int = 0) -> dict:
    """Keep four candidate instances; identical genomes retain distinct paths."""
    boundary.check_stop()
    if len(candidates) < 4:
        raise ValueError("selection needs at least four candidates")

    def rank(candidate: dict) -> tuple:
        fit = candidate["fit"]
        return (
            -fit["eff"],
            -fit["auc_L"],
            candidate["genome_sha"],
            candidate["directory"],
        )

    ranked = sorted(candidates, key=rank)
    selected, remaining, tournaments = ranked[:2], ranked[2:], []
    rng = random.Random(seed)
    while len(selected) < 4:
        entrants = rng.sample(remaining, min(3, len(remaining)))
        winner = min(entrants, key=rank)
        selected.append(winner)
        remaining.remove(winner)
        tournaments.append(
            {
                "entrants": [c["directory"] for c in entrants],
                "winner": winner["directory"],
            }
        )
    copied = []
    for candidate in remaining:
        boundary.check_stop()
        source = Path(candidate["directory"])
        target = hall / out.parent.name / source.parent.name / source.name
        boundary.safe_path(hall, target.relative_to(hall).as_posix())
        shutil.copytree(source, target)
        copied.append(str(target))

    def identity(candidate: dict) -> dict:
        return {key: candidate[key] for key in ("directory", "genome_sha")}

    report = {
        "schema": "think2-ga-select/1",
        "mu": 4,
        "lambda": 8,
        "seed": seed,
        "ranked": [identity(c) for c in ranked],
        "selected": [identity(c) for c in selected],
        "elites": [identity(c) for c in ranked[:2]],
        "tournaments": tournaments,
        "hall": copied,
    }
    write_json(out, report)
    return report
