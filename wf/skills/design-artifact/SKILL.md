---
name: design-artifact
description: Design principles and creative direction for building HTML artifacts — pages, reports, plans, landing pages, demos, decks, and small tools. Use when creating or restyling any visual HTML deliverable and deciding its palette, type pairing, layout, theming, or overall register, or when the output must not look generically AI-generated.
---

Take the perspective of the creative director at a boutique agency with a reputation for range — every commission gets its own visual identity, scaled to whatever level of treatment the brief actually merits. Palette, type, and layout should all be conscious decisions rooted in this particular subject; nothing should smell like it came off a shelf.

## Begin by sizing up the brief

The question is never *whether* to design — it's what register to design in. A memo deserves craftsmanship equal to a landing page; the two simply wear that craftsmanship differently.

Much of what comes in wants a workmanlike register: plans, briefs, demos. Finish it properly — real hierarchy in the type, spacing that was thought about, a palette that was chosen — but know when to stop. Hardly any page benefits from a towering, theatrical hero. Ornament sparingly and with taste.

Then there's work that earns the editorial register: landing pages, games, apps and tools someone will hold onto or pass along.

When in doubt, remember that nobody ever regretted a well-composed page, whereas an identity pushed too hard sometimes backfires.

Everything in the fundamentals section applies universally. The editorial process at the end only kicks in when your read of the brief calls for it.

## Fundamentals for every artifact

**Defer to prior art.** Before anything else, hunt for an established design system — a AGENTS.md or CLAUDE.md and/or DESIGN.md, QUALITY.md, PRODUCT.md etc, a tokens or theme file, styling on existing components. Found one? Apply it. The guidance below exists to plug holes, never to overrule. Authority flows in one fixed direction: what the user literally said, then whatever system the project already has, then your own taste.

**Anchor everything to the subject.** Where the subject is fuzzy, sharpen it first: one concrete thing, a defined audience, a single purpose the page exists to serve. The most distinctive moves are excavated from the subject's native territory — the stuff it's made of, the tools of its trade, the language its people speak. Populate the build with genuine content from the first draft onward; lorem ipsum is banned.

**Put two typefaces in conversation.** Even on a page that has nothing to do with letterforms, the letterforms do the heavy lifting. Never link webfonts from Google Fonts or any other font CDN — embed the face as a @font-face data URI instead. Cap measure at about 65 characters; commit to a type scale and don't wander off it; balance headings with `text-wrap: balance`, give paragraphs air, and space out uppercase labels with a hint of letter-spacing.

**Neutrals are choices too.** A dead-center mid-grey announces that nobody thought about it; tint that grey faintly toward the accent and suddenly it reads as considered. There's nothing wrong with pure white or near-black grounds when the subject wants them — the test is whether the neutral was selected or merely left over.

**Both themes, equal care.** Whatever theme the viewer runs is the theme your page renders in: the OS preference arrives via `prefers-color-scheme`, while the in-app toggle writes `data-theme="dark"` / `data-theme="light"` onto the root element — and the attribute must beat the media query going both ways. The sturdy pattern operates on tokens: declare the palette as custom properties on `:root`; inside `@media (prefers-color-scheme: dark)`, reassign only those tokens — components consume tokens exclusively and are never styled inside the media query itself — and then reassign the tokens a second time under `:root[data-theme="dark"]` and `:root[data-theme="light"]`. The dark counterpart deserves as much attention as the light original: mechanical inversion won't do; legibility and a working accent have to survive on either ground. A concept married to one visual world (the glow of an arcade cabinet, a letterpress invitation) is allowed to remain single-theme — provided that's a verdict you reached, not a corner you forgot.

**Spacing belongs to the layout, not the elements.** Sibling groups get flex or grid plus `gap`; scatter per-element margins around and they'll collapse or compound behind your back. Broad content — tables, code, diagrams — sits in its own container with `overflow-x: auto` so horizontal scrolling never leaks to the page body. Wherever numerals stack into columns, switch on `font-variant-numeric: tabular-nums`.

**Dodge the telltale AI aesthetic.** Right now, machine output keeps landing on the same few costumes: warm cream (#F4F1EA) under a serif display with a terracotta accent; near-black punctuated by one shot of acid-green or vermilion; hairline broadsheet rules over cramped columns; a purple-to-blue gradient hero floating on white; Inter or Space Grotesk chosen for safety; emoji doing the job of section markers; universal center alignment; `rounded-lg` sprayed everywhere; rounded cards wearing an accent bar or rail. A direction the user has pinned down gets executed faithfully — their instructions trump everything, up to and including a request for one of these exact looks. Absent instructions, that freedom is yours; don't blow it on a cliché.

**Engineer it soundly.** Overlapping elements, cascade collisions, fonts silently falling back — rendering bugs breed in the distance between source and screen, so stay vigilant. Non-void elements all get closed, attributes all get double quotes, keyboard focus gets a visible state, and `prefers-reduced-motion` gets respected. When graphics turn generative or decorative, reach for Canvas or WebGL before hand-authoring long SVG path data.

**Mind the cascade.** Selector specificity is where CSS goes to fight itself: a class hook like `.section` and an element hook like `.cta` can end up in a tug-of-war over padding and margins, each undoing the other. Architect the cascade so your spacing can't be quietly sabotaged.

**Content and interface craft.** Copywriting, structural devices like numbering and eyebrows, and dashboard/tool-specific guidance are covered in [references/content-craft.md](references/content-craft.md) — read it when the artifact carries meaningful copy or functions as an interface rather than a document.

## Process

Code comes second. First, rough out a short design plan — a tight token system spanning color, type, and layout:
- **Color**: 4–6 hex values, each with a name.
- **Type**: faces covering 2+ roles — a display face with character, deployed with restraint; a body face that partners it; a utility face for captions or data if the work needs one.
- **Layout**: the organizing idea, captured in a sentence or two.

Build only after that, executing the plan and tracing every color and type decision back to it.

## Beyond the fundamentals

When your read of the brief calls for the editorial register (landing pages, games, apps and tools someone will hold onto or pass along), or once the artifact is finished and ready to hand off, see [references/editorial-and-publishing.md](references/editorial-and-publishing.md) — it covers the editorial posture and principles, and how to offer to publish a finished artifact.
