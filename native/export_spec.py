"""Export the Python registry's live names and usable catalog macros."""

import json

from arcagi.dsl.registry import CATALOG, PRIMITIVES

print(json.dumps({
    "live": list(PRIMITIVES),
    "macros": {
        name: program for name, program in CATALOG.macros().items()
        if name in PRIMITIVES
    },
}, separators=(",", ":")))
