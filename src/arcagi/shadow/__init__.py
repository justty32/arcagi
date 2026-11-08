"""Shadow run: gate candidate blocks on training support and the synthetic set.

``python -m arcagi.shadow <block folder | _rule.json ...>`` scores each block
without touching the live catalog. A block passes when

1. it supports >= ``MIN_SUPPORT`` training tasks (the generators' own
   judgement on the original train pairs, ``support``);
2. in >= ``MIN_SYNTH_FRAC`` of those tasks it passes the synthetic set by
   majority: it still supports the task on >= ``CHUNK_MAJORITY`` of the
   ``data_synth`` chunks (24 synthetic pairs cut into 8 x 3); ``pred`` uses
   ``PRED_SYNTH_FRAC`` (r06: also 2/3; the design first asked for all);
3. it is no duplicate of a live block of the same kind: neither the same body
   nor the same training support set (``gate``).

Macros (``kind=macro``, ``program.json``; LLM ``transform``) are supported by
tasks whose every train pair they reproduce; they also need every step to be a
registry primitive, else the catalog would silently skip them.
"""

MIN_SUPPORT = 1
MIN_SYNTH_FRAC = 2 / 3
PRED_SYNTH_FRAC = 2 / 3  # captain r06: same as other kinds
CHUNK = 3
CHUNK_MAJORITY = 0.5
KINDS = ("formula", "pred", "extract", "macro")

__all__ = [
    "CHUNK",
    "CHUNK_MAJORITY",
    "KINDS",
    "MIN_SUPPORT",
    "MIN_SYNTH_FRAC",
    "PRED_SYNTH_FRAC",
]
