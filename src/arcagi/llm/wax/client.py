"""Minimal OpenAI-compatible chat client (LM Studio and the litellm proxy).

``google/gemma-4-e4b`` goes straight to LM Studio; it is the already loaded
model and the client never loads or unloads anything (any other LM Studio
name is refused). Every other model name goes to the user's litellm proxy
(GPT models, allowed by the user on 2026-11-09). LM Studio shares one 8k
KV cache between all callers, so "Context size has been exceeded" is usually contention: retry
with backoff until ``max_wait`` seconds have passed.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

URL = "http://localhost:1234/v1/chat/completions"
LITELLM_URL = "http://localhost:4000/v1/chat/completions"
MODEL = "google/gemma-4-e4b"
THINK = MODEL + "+think"  # same loaded model, thinking left on
# aos stopped its own e4b load at 22:48; calls before that were shared.
SHARED_UNTIL = "2026-11-09T22:48:00"


def is_local(model: str) -> bool:
    return model in (MODEL, THINK)


def url_for(model: str) -> str:
    if is_local(model):
        return URL
    if "/" in model or model.startswith("lm-"):
        raise ValueError(f"refusing LM Studio model {model!r}: only {MODEL} is loaded")
    return LITELLM_URL


@dataclass
class Reply:
    text: str = ""
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0  # wall time of the successful attempt
    wait: float = 0.0  # wall time spent on failed attempts and backoff
    retries: int = 0
    finish: str = ""
    error: str | None = None
    extra: dict = field(default_factory=dict)


def _post(body: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url_for(body["model"]),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"error": f"http {e.code}"}


def chat(
    prompt: str,
    *,
    model: str = MODEL,
    max_tokens: int = 3000,
    temperature: float = 0.8,
    max_wait: float = 600.0,
    timeout: float = 600.0,
) -> Reply:
    """One user-message completion with retry on server errors."""
    body = {
        "model": MODEL if is_local(model) else model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": False,
    }
    if is_local(model):  # reasoning models behind litellm reject temperature
        body["temperature"] = temperature
    if model == MODEL:
        # Thinking off (= litellm's lm-gemma-4-e4b-nothink): saves the shared KV.
        body["reasoning_effort"] = "none"
    rep = Reply()
    start = time.monotonic()
    delay = 3.0
    while True:
        t0 = time.monotonic()
        try:
            d = _post(body, timeout)
        except Exception as e:  # connection refused, timeout
            d = {"error": f"{type(e).__name__}: {e}"}
        if "error" not in d and d.get("choices"):
            m = d["choices"][0].get("message", {})
            u = d.get("usage", {})
            rep.text = m.get("content") or ""
            rep.reasoning = m.get("reasoning_content") or ""
            rep.prompt_tokens = u.get("prompt_tokens", 0)
            rep.completion_tokens = u.get("completion_tokens", 0)
            rep.finish = d["choices"][0].get("finish_reason") or ""
            rep.seconds = time.monotonic() - t0
            rep.wait = t0 - start
            rep.error = None
            return rep
        rep.error = str(d.get("error"))[:300]
        if time.monotonic() - start + delay > max_wait:
            rep.wait = time.monotonic() - start
            return rep
        rep.retries += 1
        time.sleep(delay)
        delay = min(delay * 1.5, 30.0)
