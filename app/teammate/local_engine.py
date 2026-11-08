"""Local, offline Gemma reply interpretation (GGUF via llama-cpp-python).

Drop-in replacement for ``ReplyEngine``: same ``interpret(recommendation, text)``
signature, same ``Reply`` result, same safety rules. A failure is never a decision,
and no user text is logged. ``llama_cpp`` is imported lazily, so the app still
starts (and falls back to Gemini/rules) when the package or model file is absent.

The prompt is built by ``build_prompt`` and is shared with tools/train_gemma_replies.py
so training and serving use byte-identical prompts.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import json
import os
import threading
import time

from .reply_engine import Reply, SCHEMA, SYSTEM_PROMPT, parse_model_output

DEFAULT_MODEL_PATH = "runtime/models/gemma-2-2b-reply.gguf"
MODEL_NAME = "gemma-2-2b-it-reply-q4_k_m"
MAX_OUTPUT_TOKENS = 160

# llama.cpp JSON-schema grammars need lowercase JSON-Schema types, not Gemini's.
GRAMMAR_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": SCHEMA["properties"]["intent"]["enum"]},
        "hours": {"type": "string"},
        "date": {"type": "string"},
        "scope_match": {"type": "boolean"},
        "needs_clarification": {"type": "boolean"},
    },
    "required": SCHEMA["required"],
    "additionalProperties": False,
}


def build_payload(recommendation, user_message: str) -> str:
    return json.dumps(
        {"recommendation": recommendation, "user_reply": user_message},
        ensure_ascii=False,
    )


def build_prompt(payload: str) -> str:
    """Gemma-2 chat format. It has no system role, so rules go in the user turn.

    No <bos> here: llama.cpp adds it when tokenizing; training tokenizers add it too.
    """
    return (
        "<start_of_turn>user\n"
        f"{SYSTEM_PROMPT}\nInput: {payload}<end_of_turn>\n"
        "<start_of_turn>model\n"
    )


class LocalGemmaEngine:
    def __init__(
        self,
        model_path=DEFAULT_MODEL_PATH,
        timeout=4.0,
        n_threads=None,
        llm=None,
    ):
        """``llm`` lets tests inject a fake; otherwise the GGUF is loaded."""
        self.model_path = model_path
        self.model = MODEL_NAME
        self.timeout = max(0.05, min(float(timeout), 10.0))
        self._llm = None
        self._grammar = None
        # llama.cpp contexts are not thread-safe: one inference at a time.
        self._lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemma")
        self.slots = threading.BoundedSemaphore(2)  # one running, one queued
        try:
            self._llm = llm or self._load(model_path, n_threads)
            self._grammar = self._make_grammar() if llm is None else None
        except Exception:
            self._llm = None

    @staticmethod
    def _load(model_path, n_threads):
        from llama_cpp import Llama  # lazy: optional dependency

        return Llama(
            model_path=model_path,
            n_ctx=2048,  # rules prompt + <=10k-char payload cap is enforced below
            n_threads=n_threads or os.cpu_count() or 4,
            verbose=False,
        )

    @staticmethod
    def _make_grammar():
        try:
            from llama_cpp import LlamaGrammar

            return LlamaGrammar.from_json_schema(json.dumps(GRAMMAR_SCHEMA))
        except Exception:
            return None  # parse_model_output still validates strictly

    @property
    def configured(self):
        return self._llm is not None

    def interpret(self, recommendation, user_message: str) -> Reply:
        start = time.monotonic()
        if not self.configured:
            return Reply("UNAVAILABLE", error_code="NOT_CONFIGURED")
        # Never truncate: truncating a late 'but...' can turn a condition into consent.
        payload = build_payload(recommendation, user_message)
        if not user_message.strip():
            return Reply("OK")
        if len(user_message) > 2000 or len(payload) > 4000:
            return Reply("UNAVAILABLE", error_code="INPUT_TOO_LONG")
        if not self.slots.acquire(blocking=False):
            return Reply("UNAVAILABLE", error_code="BUSY")
        deadline = start + self.timeout
        try:
            future = self.pool.submit(self._run, build_prompt(payload), deadline)
        except Exception:
            self.slots.release()
            return Reply("UNAVAILABLE", error_code="BUSY")
        future.add_done_callback(lambda _: self.slots.release())
        try:
            result = future.result(timeout=self.timeout)
        except FutureTimeout:
            future.cancel()
            result = Reply("UNAVAILABLE", error_code="TIMEOUT")
        except Exception:
            result = Reply("UNAVAILABLE", error_code="INVALID_OUTPUT")
        return Reply(
            **{
                **result.__dict__,
                "latency_ms": round((time.monotonic() - start) * 1000),
            }
        )

    def _run(self, prompt, deadline):
        try:
            with self._lock:
                if time.monotonic() >= deadline:
                    return Reply("UNAVAILABLE", error_code="TIMEOUT")
                kwargs = {}
                if self._grammar is not None:
                    kwargs["grammar"] = self._grammar
                    kwargs["stopping_criteria"] = self._deadline_criteria(deadline)
                output = self._llm(
                    prompt,
                    max_tokens=MAX_OUTPUT_TOKENS,
                    temperature=0.0,
                    stop=["<end_of_turn>"],
                    **kwargs,
                )
            choice = output["choices"][0]
            if choice.get("finish_reason") == "length":
                return Reply("UNAVAILABLE", error_code="INCOMPLETE_OUTPUT")
            return parse_model_output(choice["text"].strip())
        except Exception:
            return Reply("UNAVAILABLE", error_code="INVALID_OUTPUT")

    @staticmethod
    def _deadline_criteria(deadline):
        # Lets a timed-out call stop generating instead of blocking the next request.
        from llama_cpp import StoppingCriteriaList

        return StoppingCriteriaList([lambda ids, logits: time.monotonic() >= deadline])
