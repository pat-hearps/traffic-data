import json
import re
import time
from datetime import datetime

from core.utils import JEncoder, hide_keys, ms_since, obfuscate_str


def test_ms_since_format():
    t0 = time.perf_counter()
    result = ms_since(t0)
    assert re.fullmatch(r"\d+\.\d", result), f"unexpected format: {result!r}"


def test_ms_since_value():
    t0 = time.perf_counter() - 0.5  # simulate 500ms ago
    result = ms_since(t0)
    assert float(result) >= 490  # allow for timing slack


def test_obfuscate_str_default():
    s = "abcdefghij"  # 10 chars, 10% visible = ceil(1) = 1 char
    result = obfuscate_str(s)
    assert result == "a..<10chars>.."


def test_obfuscate_str_custom_pct():
    s = "abcdefghij"  # 10 chars, 50% visible = 5 chars
    result = obfuscate_str(s, pct_visible=0.5)
    assert result == "abcde..<10chars>.."


def test_obfuscate_str_non_string_input():
    result = obfuscate_str(12345)
    assert result.startswith("1")
    assert "chars" in result


def test_hide_keys_obfuscates_key_fields():
    d = {"KeyID": "supersecret", "other": "value", "apikey": "also-secret"}
    result = hide_keys(d)
    assert result["other"] == "value"
    assert "supersecret" not in result["KeyID"]
    assert "also-secret" not in result["apikey"]


def test_hide_keys_case_insensitive():
    d = {"KEY": "secret", "Key": "secret", "key": "secret", "myKey": "secret", "MYKEY": "secret"}
    result = hide_keys(d)
    for k, v in result.items():
        assert "chars" in v, f"expected {k!r} value to be obfuscated, got {v!r}"


def test_hide_keys_non_key_fields_unchanged():
    d = {"url": "http://example.com", "token": "abc123", "Cache-Control": "no-cache"}
    result = hide_keys(d)
    assert result == d


def test_jencoder_datetime():
    dt = datetime(2025, 3, 5, 3, 48, 0)
    result = json.dumps({"t": dt}, cls=JEncoder)
    assert '"2025-03-05T03:48:00"' in result


def test_jencoder_passthrough_types():
    data = {"n": 42, "s": "hello", "lst": [1, 2]}
    result = json.loads(json.dumps(data, cls=JEncoder))
    assert result == data


def test_jencoder_unserializable_raises():
    class Unserializable:
        pass

    try:
        json.dumps({"x": Unserializable()}, cls=JEncoder)
        assert False, "should have raised TypeError"
    except TypeError:
        pass
