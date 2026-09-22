#!/usr/bin/env python3
"""Static validation for a self-contained HTML slideshow."""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class DeckParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.slides = 0
        self.notes = 0
        self.external_refs: list[str] = []
        self.slide_depth = 0
        self.slide_text: list[str] = []
        self.current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "section" and "slide" in classes:
            self.slides += 1
            self.slide_depth = 1
            self.current_text = []
            if "data-notes" in values:
                self.notes += 1
        elif self.slide_depth:
            self.slide_depth += 1

        if tag in {"script", "link", "img", "source", "video", "audio", "iframe"}:
            for key in ("src", "href"):
                value = values.get(key)
                if value and not value.startswith(("data:", "#")):
                    self.external_refs.append(value)

    def handle_endtag(self, tag: str) -> None:
        if not self.slide_depth:
            return
        self.slide_depth -= 1
        if self.slide_depth == 0:
            self.slide_text.append(" ".join(self.current_text).strip())

    def handle_data(self, data: str) -> None:
        if self.slide_depth:
            cleaned = " ".join(data.split())
            if cleaned:
                self.current_text.append(cleaned)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html_file", type=Path)
    args = parser.parse_args()

    path = args.html_file.resolve()
    if not path.is_file():
        print(f"ERROR: file not found: {path}")
        return 2

    text = path.read_text(encoding="utf-8")
    deck = DeckParser()
    try:
        deck.feed(text)
        deck.close()
    except Exception as exc:
        print(f"ERROR: HTML parsing failed: {exc}")
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    if deck.slides < 2:
        errors.append("expected at least 2 <section class=\"slide\"> elements")
    if deck.notes != deck.slides:
        errors.append(f"every slide needs data-notes ({deck.notes}/{deck.slides})")
    if deck.external_refs:
        errors.append("external references found: " + ", ".join(sorted(set(deck.external_refs))))

    requirements = {
        "responsive 16:9 canvas": "16 / 9",
        "deck theme marker": 'id="deck-theme"',
        "shared style marker": 'id="slides-core"',
        "shared runtime marker": 'id="slides-runtime"',
        "print stylesheet": "@media print",
        "progress bar": 'class="progress"',
        "overview control": "toggleOverview",
        "fullscreen control": "requestFullscreen",
        "notes control": "notesOpen",
        "hash navigation": "location.hash",
        "keyboard navigation": "ArrowRight",
    }
    for label, needle in requirements.items():
        if needle not in text:
            errors.append(f"missing {label}")

    placeholders = re.findall(r"\b(?:TODO|TBD|LOREM IPSUM|REPLACE ME)\b", text, flags=re.IGNORECASE)
    if placeholders:
        errors.append("unresolved placeholders found")

    empty_slides = [str(i + 1) for i, value in enumerate(deck.slide_text) if not value]
    if empty_slides:
        errors.append("empty slide(s): " + ", ".join(empty_slides))

    long_slides = [str(i + 1) for i, value in enumerate(deck.slide_text) if len(value) > 900]
    if long_slides:
        warnings.append("very dense slide text; inspect visually: " + ", ".join(long_slides))

    print(f"Slides: {deck.slides}")
    print(f"Speaker notes: {deck.notes}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        return 1
    print("OK: slideshow passed static validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
