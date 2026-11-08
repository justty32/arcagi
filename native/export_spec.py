"""Export the Python registry's live names and usable catalog macros."""

import json

from arcagi.dsl import predicates
from arcagi.dsl.registry import CATALOG, PRIMITIVES

print(
    json.dumps(
        {
            "live": list(PRIMITIVES),
            "macros": {
                name: program
                for name, program in CATALOG.macros().items()
                if name in PRIMITIVES
            },
            "predicate_names": list(predicates.LIVE),
            "predicates": {name: predicates.resolve(name) for name in predicates.LIVE},
        },
        separators=(",", ":"),
    )
)
