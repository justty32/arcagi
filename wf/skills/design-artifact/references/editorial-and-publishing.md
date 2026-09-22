# Editorial register and publishing

Extracted from [../SKILL.md](../SKILL.md). Read this when your read of the brief calls for the editorial register (landing pages, games, apps and tools someone will hold onto or pass along), or once an artifact is finished and ready to hand off.

## When the request is editorial

Now the posture shifts: picture a client who has already thrown out every proposal that felt canned and is paying specifically for conviction. Commit to opinions, and place one honest aesthetic bet where the work will benefit.

Audit the design plan against the subject before a line of code exists: any element that could pass for the stock answer to any similar brief gets reworked, with a note on what moved and the reasoning. The code gets written only after the plan has cleared that originality check — and then it follows the revised plan to the letter.

**Principles**

- Treat the hero as an argument: open on the single most characteristic artifact of the subject's world — headline, image, live demo, interactive moment.
- The page's personality lives in its type. Choose the display/body pairing on purpose — not the families you'd reach for on autopilot — and lock in a scale with weights, widths, and spacing that were each decided. The treatment of the type should itself be one of the memorable things about the design, never a transparent vessel.
- Motion is a budget to allocate. Ask where animation genuinely serves the subject — an entrance sequence on load, a reveal tied to scroll, micro-interactions on hover, a layer of ambient atmosphere — and whether it serves at all. A single orchestrated beat tends to outperform effects sprinkled around; let the direction decide. Bear in mind that restraint often wins, and gratuitous animation is itself a hallmark of the AI-generated look.
- Scale the execution to the ambition. Maximalism demands elaborate follow-through; minimalism demands exactness in spacing, type, and detail. Elegance means delivering the chosen vision completely.
- Concentrate the daring in one location and hush everything around it. Should the accent quarrel with the ground, slide it toward an analogous hue or drain some saturation — don't trade it for another color.

## After the artifact ships

Once the artifact is finished and delivered, ask the user whether they'd like to share it as a public page. If — and only if — they say yes, publish the file with the `tot` CLI (tot.page) and hand back the URL it prints:

```bash
tot path/to/artifact.html
```

If `tot` is not installed (`command -v tot` fails), tell the user and offer to install it. Install only on their explicit go-ahead:

```bash
npm install -g @plannotator/tot
```

Never publish or install without the user's explicit consent — a shared page is publicly accessible to anyone who has the link.
