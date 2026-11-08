# identity baseline

Solver `identity` (top-1 exact match), data revision 399030444e0ab0cc8b4e199870fb20b863846f34.

| split | tasks_correct / tasks_total | tests_correct / tests_total | errors |
|---|---|---|---|
| evaluation | 0 / 400 | 0 / 419 | 0 |
| training | 0 / 400 | 0 / 416 | 0 |

Commands (full per-task JSON is not committed; regenerate it with these):

    uv run arcagi eval --split evaluation --solver identity --output reports/baseline-identity/identity-evaluation.json
    uv run arcagi eval --split training --solver identity --output reports/baseline-identity/identity-training.json
