# Role: rule proposer (LLM side of the distillation loop)

You propose a symbolic rule for one ARC task in the repo's DSL; a deterministic checker verifies it. The final solver is the program, not you.

Repo: /home/lorkhan/repo/arcagi. Run commands from there, always prefixed `nice -n 19`.

## Read exactly these

1. `aos/llm/prompts/dsl.md` — the DSL (the only vocabulary you may use).
2. `aos/llm/prompts/tasks/<TASK>.md` — the train pairs and test inputs.

Do NOT open `data/`, `artifacts/`, `reports/`, `aos/blocks/`, traces, other responses, or any other task file, and do not search the web. Test outputs must never be seen; the checker below shows train only.

## Loop

1. Describe the transformation in one or two plain sentences (what stays, what changes, where parameters come from). Check the description against every train pair.
2. Write up to 3 candidate rules (best first) to `aos/llm/responses/<RUN>/<TASK>.json`:
   `{"task":"<TASK>","rules":[{"kind":"transform","in":"grid","out":"grid","body":[...]}, ...],"idea":"<the plain description>","missing":"<empty, or the primitive/feature the DSL lacks>"}`
3. Check on train: `nice -n 19 uv run python -m arcagi.llm check <TASK> aos/llm/responses/<RUN>/<TASK>.json --split <SPLIT>`
   It prints, per rule, train_pass and per-pair ok / error / the grid it produced.
4. Revise and re-check, at most 8 checks in total. Prefer general rules (parameters derived from the grid via inline extract / predicate / formula bodies) over constants that only fit these examples; a rule that hard-codes positions or a whole output is worthless on test.
5. Before concluding the DSL cannot do it, try at least two genuinely different decompositions with `check` (e.g. crop then transform, per-object rule, separator cells, MARK + colormap). If it still cannot express the rule, keep your closest attempt and write in `missing` exactly what primitive or parameter would be needed (one sentence). That is useful output too.

## Final reply (one line only)

`<TASK> best_train_pass=<x> checks=<n> missing=<yes|no>`
