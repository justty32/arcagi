---
name: markdown-html-slides
description: Convert one or more Markdown files into a polished, self-contained, browser-playable HTML slide deck. Use when Markdown should become a presentation, briefing, talk, review deck, or slideshow without requiring native PowerPoint or Google Slides output. Do not use when the requested deliverable must be an editable PPTX or native Google Slides deck.
---

# Markdown HTML Slides

Turn source Markdown into a concise presentation rather than displaying the documents verbatim. The HTML deck is the speaking layer; the Markdown remains the detailed reference.

## Workflow

1. Read every source Markdown file completely. Inspect explicitly named project files or references only to understand the subject; do not expand the presentation beyond the user's requested scope.
2. Establish an audience contract before outlining: technical background, familiarity with the domain, desired tone, acceptable information density, language, and any jargon or topics to avoid. Treat requirements supplied at invocation time as binding. Ask only when a missing choice would materially change the deck; under time pressure, make a reasonable assumption and proceed.
3. Translate the source for that audience. Replace unfamiliar jargon with plain language, define unavoidable terms once in context, expand acronyms on first use, and use concrete examples or comparisons when they improve understanding. Preserve technical accuracy; simplifying language must not change the underlying claim.
4. Create a cumulative narrative. Default to 6–12 slides, one claim per slide, with a minimal cover and a conclusion that resolves the opening. Do not use an agenda as a substitute for a narrative.
5. Separate presentation content from reference detail. Keep high-value comparisons, decisions, relationships, and implications on slides; leave exhaustive tables and field-by-field detail in the Markdown unless specifically requested.
6. Read [references/design-system.md](references/design-system.md), then start from [assets/slideshow-shell.html](assets/slideshow-shell.html). Copy the shell to the requested output path and replace its sample slides with audience-facing content.
7. Produce exactly one self-contained `.html` file by default. Keep CSS and JavaScript inline and use no CDN, remote font, build step, server, or external runtime. Do not create a playback guide, README, PDF, screenshots, or other companion files unless requested.
8. Preserve the `deck-theme`, `slides-core`, and `slides-runtime` element IDs. Put deck-specific colors and small overrides in `deck-theme`; keep reusable layout/runtime code in the other two blocks. This lets a later optimization pass extract shared assets safely.
9. Add a concise `data-notes` value to every slide. Notes may contain talk-track context and source filenames, but visible slide copy must never expose planning notes or production commentary.
10. Preserve the shell's keyboard controls, URL hash, progress bar, overview, notes, fullscreen, and print styles. Adapt colors and layouts when the content benefits, while keeping the interaction contract intact.
11. Run `python scripts/validate_slideshow.py <output.html>`. Fix every error and review warnings. When browser control is available, open the file, inspect every slide at presentation size, exercise navigation and overview mode, and fix clipping, wrapping, overflow, low contrast, or inconsistent alignment.
12. Deliver the HTML with a short summary. Mention only the few controls needed to start presenting; do not generate a separate instruction file.

## Content Constraints

- Obey explicit exclusions such as “do not discuss implementation,” even when related source files contain that material.
- Do not invent facts, metrics, decisions, or scope. Surface unresolved source ambiguity neutrally only when the audience needs to decide it.
- Prefer familiar words for non-expert audiences. If a technical identifier must remain visible, pair it with a plain-language label or explanation.
- Do not confuse plain language with childish language. Match the audience's altitude and keep the presenter credible.
- Prefer takeaway titles that can be spoken aloud. Avoid generic labels such as “Overview” when a claim is available.
- Use code formatting for identifiers and technical tokens, not for ordinary prose.
- Avoid shrinking text to rescue an overcrowded slide. Shorten, split, or change the layout.

## Output Contract

- One portable UTF-8 HTML file that opens directly from disk.
- 16:9 responsive slide canvas.
- Keyboard: arrows/PageUp/PageDown/Space, Home/End, `F`, `O`, and `N`.
- Printable one-slide-per-page output.
- No unresolved placeholders, external dependencies, or auxiliary files by default.
