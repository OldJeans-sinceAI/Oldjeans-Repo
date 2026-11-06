import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core
import render


def test_norm_name_strips_legal_forms():
    assert core.norm_name("Esimerkki Oy") == "esimerkki"


def test_digits_tail():
    assert core.digits_tail("+358 40 123 4567") == "401234567"
    assert core.digits_tail("040 123 4567") == "401234567"


def test_is_public_url_blocks_local():
    assert not core.is_public_url("http://127.0.0.1/")
    assert not core.is_public_url("file:///etc/passwd")


def test_verdict_ranges():
    assert render.verdict(80)[0] == "Hyvä näkyvyys"
    assert render.verdict(50)[0] == "Kohtalainen näkyvyys"
    assert render.verdict(10)[0] == "Heikko näkyvyys"


def test_render_escapes_input():
    r = {"company": "<script>x</script>", "city": "", "phone": "", "score": 0,
         "channels": [], "site": None, "recs": [], "found_channels": 0}
    assert "<script>" not in render.body(r)
