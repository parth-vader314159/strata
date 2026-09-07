"""
strata.parse.triage
===================
Deciding which grammar owns a line, and how sure we are.

TWO-PHASE, AND WHY

Phase 1 -- SHAPE. One cheap character-counting pass over the line yields its
structural family (see `shapes`). Grammars are bucketed by family at load
time, so a JSON line only ever considers JSON grammars. This is what keeps
classification roughly constant in the number of grammars: onboarding the
fiftieth source does not slow down the other forty-nine.

Phase 2 -- SIGNATURE. Only the handful of same-family candidates get their
literals and regexes evaluated, cheapest test first.

CONFIDENCE, AND THE AMBIGUITY RULE

A score is not enough on its own. If two grammars both claim a line at 0.9,
we are not 90% confident -- we are confused, and the raw number hides it.
So when the runner-up is close behind the leader, the leader's confidence is
cut. That turns a silent coin-flip into a visible quarantine.

This matters more than accuracy: a misidentified log confidently parsed into
the wrong fields is worse than an unparsed one, because it looks correct and
nothing alerts. Unknown beats wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from .compiler import CompiledGrammar
from .shapes import Fingerprint, Shape, fingerprint

# How close the runner-up may be before we call the decision ambiguous.
AMBIGUITY_MARGIN = 0.12
# Multiplier applied to the leader when the field is too close to call.
AMBIGUITY_PENALTY = 0.55
# Below this, a line goes to quarantine rather than into the clean stream.
DEFAULT_FLOOR = 0.70


@dataclass(slots=True)
class Decision:
    grammar: CompiledGrammar | None
    confidence: float
    shape: Shape
    contenders: int = 0
    runner_up: str | None = None

    @property
    def accepted(self) -> bool:
        return self.grammar is not None


class Triage:
    """Shape-bucketed grammar selection."""

    __slots__ = ("_by_shape", "_universal", "_all", "floor", "_stats")

    def __init__(self, compiled: list[CompiledGrammar], floor: float = DEFAULT_FLOOR) -> None:
        self.floor = floor
        self._all = list(compiled)
        self._by_shape: dict[Shape, list[CompiledGrammar]] = {}
        # Grammars declaring FREEFORM are the catch-all: prose lines are the
        # residual category, and a source whose shape we misjudge should still
        # get a chance rather than being dismissed on a heuristic.
        self._universal: list[CompiledGrammar] = []

        for g in compiled:
            self._by_shape.setdefault(g.shape, []).append(g)
            if g.shape is Shape.FREEFORM:
                self._universal.append(g)

        self._stats = {"lines": 0, "shape_hits": 0, "evaluated": 0}

    # ------------------------------------------------------------------ query

    def candidates(self, shape: Shape) -> list[CompiledGrammar]:
        same = self._by_shape.get(shape, ())
        if shape is Shape.FREEFORM:
            return list(same)
        return [*same, *self._universal]

    def decide(self, line: str, fp: Fingerprint | None = None) -> Decision:
        """Select a grammar for one line."""
        fp = fp or fingerprint(line)
        pool = self.candidates(fp.shape)

        self._stats["lines"] += 1
        self._stats["evaluated"] += len(pool)
        if pool:
            self._stats["shape_hits"] += 1

        if not pool:
            return Decision(None, 0.0, fp.shape, 0)

        best: CompiledGrammar | None = None
        best_score = 0.0
        second = 0.0
        second_id: str | None = None

        for g in pool:
            score = g.matches(line)
            if score > best_score:
                second, second_id = best_score, (best.id if best else None)
                best, best_score = g, score
            elif score > second:
                second, second_id = score, g.id

        if best is None or best_score <= 0.0:
            return Decision(None, 0.0, fp.shape, len(pool))

        confidence = best_score
        if second > 0.0 and (best_score - second) < AMBIGUITY_MARGIN:
            confidence *= AMBIGUITY_PENALTY

        return Decision(best, round(confidence, 3), fp.shape, len(pool), second_id)

    # ------------------------------------------------------------------ stats

    def selectivity(self) -> dict:
        """How well shape bucketing is working.

        `grammars_per_line` is the number actually evaluated per line. Compare
        it with the total: the gap is the work the shape pass avoided, and it
        is the number to quote when someone asks whether this scales to
        hundreds of sources.
        """
        lines = self._stats["lines"] or 1
        return {
            "grammars_total": len(self._all),
            "grammars_per_line": round(self._stats["evaluated"] / lines, 2),
            "shape_hit_rate": round(self._stats["shape_hits"] / lines, 4),
            "lines_triaged": self._stats["lines"],
            "work_avoided": round(
                1 - (self._stats["evaluated"] / (lines * max(len(self._all), 1))), 4),
        }

    def families(self) -> dict[str, list[str]]:
        return {shape.label: sorted(g.id for g in gs)
                for shape, gs in sorted(self._by_shape.items())}
