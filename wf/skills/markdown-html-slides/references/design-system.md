# HTML Slideshow Design System

Use this reference while adapting the slideshow shell.

## Communication

Define the job in one sentence: by the end, the audience should understand, choose, approve, or discuss something because of the deck's central takeaway.

Build a logical arc appropriate to the material, such as:

- current state → change → future state;
- question → evidence → answer;
- problem → causes/options → recommendation;
- concept → structure → examples → implications.

Each slide should do one job and make one primary claim. Visible content is for the audience, never for the person producing the deck.

## Audience and Language

Before writing slides, record a compact audience lens:

- technical background and domain familiarity;
- what the audience already knows;
- what they need to understand or decide;
- desired tone and language;
- acceptable jargon and terms to avoid;
- desired depth and presentation duration, when supplied.

For a non-technical or mixed audience:

- lead with the consequence or purpose before the mechanism;
- replace specialist nouns with familiar verbs and concrete descriptions;
- define a necessary technical term beside its first use rather than in a glossary slide;
- expand acronyms on first use;
- pair identifiers, schemas, formulas, or code with a plain-language interpretation;
- avoid stacking several unfamiliar terms in one sentence.

Do not remove distinctions that matter to correctness. When there is no precise plain-language substitute, retain the term and explain it briefly.

## Density

- Cover: title, short subtitle, optional eyebrow; keep it sparse.
- Ordinary slide: one title plus one dominant composition.
- Default body copy: no more than roughly 60–90 Chinese characters or 45–70 English words per region.
- Tables: use only rows required for the spoken point. Move exhaustive detail back to the source Markdown.
- If content does not fit, split the slide before reducing font size.

## Typography

At a 1280×720 viewport, target at least:

- deck title: 64 px;
- slide title: 40 px;
- subheading/callout: 24 px;
- body: 18 px;
- footers and small labels: 13 px.

Use `clamp()` for responsive sizing. Prefer system font stacks so the file remains portable. Keep one-line titles on one line when practical; shorten them if they wrap unexpectedly.

## Composition

Use a flat editorial composition with generous margins and one dominant relationship. Vary adjacent silhouettes. Useful patterns include:

- large message or cover;
- two-column comparison;
- three- or four-part principle layout;
- process/timeline;
- evidence table plus interpretation;
- hierarchy or grouped model;
- one large callout with supporting explanation.

Avoid repeating a dashboard-like grid of small cards throughout the deck. Use panels only when they express a real grouping or comparison. Prefer thin rules, whitespace, and deliberate alignment over heavy shadows or ornament.

## Color

Start with the shell's neutral palette. Use one strong accent and at most one secondary accent for meaning. Ensure body text contrast remains high. Do not encode essential meaning by color alone; pair color with labels or position.

## Interaction Contract

Preserve these behaviors from the shell:

- next: Right, Down, PageDown, Space;
- previous: Left, Up, PageUp;
- first/last: Home/End;
- fullscreen: `F`;
- overview: `O`, with click-to-open;
- speaker notes: `N`;
- current slide in `#slide-N`;
- progress bar;
- print CSS with one slide per page.

## Quality Review

Inspect every slide at 16:9 presentation size. Check:

- title and body wrapping;
- content clipping or overflow;
- table row density;
- alignment and equal outer margins;
- contrast and hierarchy;
- slide-to-slide rhythm;
- overview-mode usability;
- notes content and source traceability;
- keyboard navigation and fullscreen behavior.
