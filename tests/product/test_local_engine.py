import json
import threading
import time
import unittest

from app.teammate.local_engine import LocalGemmaEngine, build_prompt
from app.teammate.reply_engine import SYSTEM_PROMPT

REC = {"change": {"kind": "DATE_HOURS", "date": "2026-12-24", "hours": "07:30-13:00"}}
GOOD = {
    "intent": "EDIT",
    "hours": "07:30-15:00",
    "date": "2026-12-24",
    "scope_match": True,
    "needs_clarification": False,
}


class FakeLlm:
    def __init__(self, text=None, finish="stop", delay=0.0, boom=False):
        self.text = json.dumps(GOOD) if text is None else text
        self.finish, self.delay, self.boom = finish, delay, boom
        self.prompts = []

    def __call__(self, prompt, **kw):
        self.prompts.append((prompt, kw))
        if self.boom:
            raise RuntimeError("oom")
        time.sleep(self.delay)
        return {"choices": [{"text": self.text, "finish_reason": self.finish}]}


class LocalEngineTests(unittest.TestCase):
    def engine(self, **kw):
        timeout = kw.pop("timeout", 2.0)
        return LocalGemmaEngine("x.gguf", timeout=timeout, llm=FakeLlm(**kw))

    def test_valid_output_becomes_ok_reply(self):
        e = self.engine()
        r = e.interpret(REC, "Please close at 15:00 instead")
        self.assertEqual((r.status, r.intent, r.hours), ("OK", "EDIT", "07:30-15:00"))
        self.assertTrue(r.scope_match)
        self.assertFalse(r.needs_clarification)

    def test_prompt_uses_gemma_template_rules_and_unescaped_unicode(self):
        e = self.engine()
        e.interpret(REC, "Sopii, mutta suljetaan jo klo 14")
        prompt, kw = e._llm.prompts[0]
        self.assertTrue(prompt.startswith("<start_of_turn>user\n" + SYSTEM_PROMPT))
        self.assertTrue(prompt.endswith("<end_of_turn>\n<start_of_turn>model\n"))
        self.assertIn("Sopii, mutta", prompt)
        self.assertEqual(kw["temperature"], 0.0)
        self.assertEqual(build_prompt("{}").count("<start_of_turn>"), 2)

    def test_malformed_or_wrong_schema_is_unavailable_never_decision(self):
        for text in ["not json", "{}", json.dumps({**GOOD, "intent": "MAYBE"}),
                     json.dumps({**GOOD, "scope_match": "true"}),
                     json.dumps({**GOOD, "extra": 1})]:
            r = self.engine(text=text).interpret(REC, "hello there")
            self.assertEqual((r.status, r.error_code), ("UNAVAILABLE", "INVALID_OUTPUT"))
            self.assertIsNone(r.decision)

    def test_truncated_generation_is_incomplete(self):
        r = self.engine(finish="length").interpret(REC, "hello there")
        self.assertEqual(r.error_code, "INCOMPLETE_OUTPUT")

    def test_runtime_error_is_unavailable(self):
        r = self.engine(boom=True).interpret(REC, "hello there")
        self.assertEqual((r.status, r.error_code), ("UNAVAILABLE", "INVALID_OUTPUT"))

    def test_timeout(self):
        r = self.engine(delay=0.5, timeout=0.1).interpret(REC, "hello there")
        self.assertEqual((r.status, r.error_code), ("UNAVAILABLE", "TIMEOUT"))

    def test_busy_when_saturated(self):
        e = self.engine(delay=0.4)
        out = []
        ts = [threading.Thread(target=lambda: out.append(e.interpret(REC, "hello"))) for _ in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertIn("BUSY", [r.error_code for r in out])

    def test_input_limits_and_empty(self):
        e = self.engine()
        self.assertEqual(e.interpret(REC, "x" * 2001).error_code, "INPUT_TOO_LONG")
        self.assertEqual(e.interpret(REC, "   ").status, "OK")
        self.assertEqual(e._llm.prompts, [])

    def test_missing_model_is_not_configured(self):
        e = LocalGemmaEngine("/nonexistent/model.gguf")  # llama_cpp or file missing
        self.assertFalse(e.configured)
        self.assertEqual(e.interpret(REC, "hello").error_code, "NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
