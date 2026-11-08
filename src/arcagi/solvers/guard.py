"""Source-agnostic guard over train-consistent candidates (r07 line C).

A *candidate* is one program that reproduced every train pair, with its test
outputs already computed (Python search, native C++ search, or anything else:
the guard never looks at the origin). ``judge`` re-ranks the candidates and
may abstain; it is pure and never runs programs (``gated.evaluate`` does).

Gates:

* ``support`` (a): an output produced by fewer than ``min_support`` distinct
  programs is *demoted* behind every supported output. Demotion is not
  removal: when no supported output exists, the original order is kept.
* ``unseen`` (b): a test output containing a color that appears in no train
  output and not in its own test input is *distrusted* (removed).
* ``synth`` (c): when the task has synthetic pairs, a candidate that fails
  any of the checked synthetic pairs is distrusted. Tasks without synthetic
  pairs (evaluation) skip the gate automatically.
* ``table`` (d, added in r07): a memorizing cell table is distrusted. When a
  ``local_rule``/``x_vrule`` table has at least ``TABLE_MIN_ROWS`` rows and
  more than half of them are *thin* (their key changes fewer than
  ``ROW_SUPPORT`` train cells), the table writes the answer cell by cell
  instead of learning a rule. This is the Python learners' own anti-
  memorization rule (``MIN_SUPPORT = 2``) applied to every source: the
  native fitters do not enforce it. r06 training: 35 of 57 train-passing
  wrong answers carry such a table, 0 right answers do.
* ``shape`` (e, added in r07): a shape law every train pair obeys must hold
  on test too: when every train output has its input's shape, or every train
  output has one fixed shape, a test output breaking that law is distrusted.

When every candidate is distrusted the guard abstains (echo test inputs, as
the solvers do without a solution).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from arcagi.tasks import Grid

GATES = ("support", "unseen", "synth", "table", "shape")
# Production default (r07 offline study on r06 training): a synth veto drops
# ~60 right answers (RE-ARC pairs vary colors/sizes the task never varies),
# so synth only demotes; support and shape cost right answers for no gain.
DEFAULT_GATES = ("unseen", "synth", "table")
DEFAULT_SYNTH_DEMOTE = True
MIN_SUPPORT = 2
ROW_SUPPORT = 2  # = learners.MIN_SUPPORT
# With <= 3 rows a single thin row decides the majority; such tables cost
# less than one program step and are left to the other gates.
TABLE_MIN_ROWS = 4

type Key = tuple[Grid, ...]


@dataclass(frozen=True)
class Candidate:
    """One train-consistent program and what it does on test (and synth) inputs.

    ``tests`` is None when the program could not be re-run; such a candidate
    keeps its place but can only be judged by gates that need no outputs.
    ``synth_ok``/``synth_total`` count synthetic pairs reproduced (total 0 =
    not checked). ``table`` is ``(rows, thin rows)`` over the program's
    cell-table steps (None = no such step).
    """

    program: str
    tests: tuple[Grid, ...] | None
    origin: str = "unknown"
    synth_ok: int = 0
    synth_total: int = 0
    table: tuple[int, int] | None = None


@dataclass
class Judged:
    candidate: Candidate
    support: int
    reasons: list[str] = field(default_factory=list)  # distrust reasons
    demoted: bool = False

    @property
    def trusted(self) -> bool:
        return not self.reasons


@dataclass
class Verdict:
    predictions: list[Grid]
    chosen: Judged | None
    ranked: list[Judged]  # trusted first (supported before demoted), then the rest
    abstained: bool
    reason: str


def _key(tests: Sequence[Grid]) -> Key:
    return tuple(tuple(tuple(row) for row in grid) for grid in tests)


def colors(grid: Grid) -> set[int]:
    return {v for row in grid for v in row}


def unseen_colors(
    tests: Sequence[Grid], train_outputs: Sequence[Grid], test_inputs: Sequence[Grid]
) -> set[int]:
    """Colors of each test output found neither in train outputs nor its input."""
    known = set().union(*(colors(o) for o in train_outputs)) if train_outputs else set()
    out: set[int] = set()
    for grid, given in zip(tests, test_inputs, strict=False):
        out |= colors(grid) - known - colors(given)
    return out


def shape(grid: Grid) -> tuple[int, int]:
    return (len(grid), len(grid[0]) if grid else 0)


def shape_breaks(
    tests: Sequence[Grid],
    train: Sequence[tuple[Grid, Grid]],
    test_inputs: Sequence[Grid],
) -> str | None:
    """Name the train shape law a test output breaks, or None."""
    if not train:
        return None
    if all(shape(i) == shape(o) for i, o in train):
        for out, given in zip(tests, test_inputs, strict=False):
            if shape(out) != shape(given):
                return "train keeps input shape"
    fixed = {shape(o) for _i, o in train}
    if len(fixed) == 1 and any(shape(out) not in fixed for out in tests):
        return f"train outputs all {next(iter(fixed))}"
    return None


def memorizes(table: tuple[int, int] | None) -> bool:
    """True when most rows of a big enough cell table lack train evidence."""
    if table is None:
        return False
    rows, thin = table
    return rows >= TABLE_MIN_ROWS and 2 * thin > rows


def support_counts(candidates: Sequence[Candidate]) -> dict[Key, int]:
    """Distinct programs per test output (candidates without outputs skipped)."""
    programs: dict[Key, set[str]] = {}
    for c in candidates:
        if c.tests is not None:
            programs.setdefault(_key(c.tests), set()).add(c.program)
    return {k: len(v) for k, v in programs.items()}


def judge(
    candidates: Sequence[Candidate],
    train: Sequence[tuple[Grid, Grid]],
    test_inputs: Sequence[Grid],
    *,
    gates: Collection[str] = DEFAULT_GATES,
    min_support: int = MIN_SUPPORT,
    synth_demote: bool = DEFAULT_SYNTH_DEMOTE,
) -> Verdict:
    """Re-rank ``candidates`` (given in the solver's own order) and pick top-1.

    ``train`` holds the (input, output) pairs; ``test_inputs`` the test grids.
    ``synth_demote`` turns the synth gate from distrust into demotion (like
    ``support``): failing candidates rank behind passing ones but stay.
    """
    unknown = set(gates) - set(GATES)
    if unknown:
        raise ValueError(f"unknown gates: {sorted(unknown)}")
    train_outputs = [o for _i, o in train]
    counts = support_counts(candidates)
    judged: list[Judged] = []
    for c in candidates:
        j = Judged(c, counts.get(_key(c.tests), 0) if c.tests is not None else 0)
        if "unseen" in gates and c.tests is not None:
            new = unseen_colors(c.tests, train_outputs, test_inputs)
            if new:
                j.reasons.append(f"unseen colors {sorted(new)}")
        synth_fail = "synth" in gates and c.synth_total and c.synth_ok < c.synth_total
        if synth_fail and not synth_demote:
            j.reasons.append(f"synth {c.synth_ok}/{c.synth_total}")
        if "table" in gates and memorizes(c.table):
            j.reasons.append(f"table {c.table[1]}/{c.table[0]} thin rows")
        if "shape" in gates and c.tests is not None:
            broken = shape_breaks(c.tests, train, test_inputs)
            if broken:
                j.reasons.append(f"shape: {broken}")
        j.demoted = ("support" in gates and j.support < min_support) or bool(
            synth_fail and synth_demote
        )
        judged.append(j)
    # Stable: original order inside each class.
    ranked = sorted(judged, key=lambda j: (not j.trusted, j.demoted))
    best = ranked[0] if ranked else None
    echo = [_lists(g) for g in test_inputs]
    if best is None:
        return Verdict(echo, None, ranked, True, "no candidates")
    if not best.trusted:
        return Verdict(echo, None, ranked, True, "all distrusted")
    if best.candidate.tests is None:
        return Verdict(echo, None, ranked, True, "top has no outputs")
    original = judged[0]
    if best is original:
        reason = "kept"
    elif not original.trusted:
        reason = "switched: top-1 distrusted (" + "; ".join(original.reasons) + ")"
    else:
        reason = "switched: top-1 demoted (support or synth)"
    predictions = [_lists(g) for g in best.candidate.tests]
    return Verdict(predictions, best, ranked, False, reason)


def _lists(grid: Grid) -> list[list[int]]:
    return [list(row) for row in grid]
