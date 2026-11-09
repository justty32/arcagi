"""Night run 2026-11-09: cast wax with a model, measure empty-tree fit.

The model only proposes step-by-step ``solve`` code; the trajectory is
produced and checked locally, and each step is fitted by the empty tree
(``arcbatch seed-sub``). Modules: ``client`` (LM Studio / litellm),
``prompts`` (methods), ``sandbox`` (run code -> trajectory), ``fit``
(segment fitting with cache), ``runner`` (loop, stats), ``__main__`` (CLI).
"""
