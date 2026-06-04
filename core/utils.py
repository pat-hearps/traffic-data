import json
import time
from datetime import datetime
from math import ceil


class JEncoder(json.JSONEncoder):
    """Handle datetimes in json"""

    # Override default() method
    def default(self, obj):
        # Datetime to isoformat string
        if isinstance(obj, datetime):
            return obj.isoformat()

        # Default behavior for all other types
        return super().default(obj)


def ms_since(t0: float) -> str:
    """Return elapsed milliseconds since a time.perf_counter() start, formatted to 1 decimal point."""
    return f"{(time.perf_counter() - t0) * 1000:.1f}"


def hide_keys(indict: dict) -> dict:
    """Returns same input dict with only one type of change:
    If the term 'key' appears in the key of the dict, the value is
    obfuscated to hide most of the string."""
    hidden = dict()
    for name, value in indict.items():
        if "key" in name.lower():
            hidden[name] = obfuscate_str(value)
        else:
            hidden[name] = value
    return hidden


def obfuscate_str(instring: str, pct_visible: float = 0.1) -> str:
    """Obfuscate all but first 10% (or value set by param 'pct_visible') of an input string"""
    if not isinstance(instring, str):
        instring = str(instring)
    str_len = len(instring)
    n_chars_vis = int(ceil(pct_visible * str_len))
    return f"{instring[:n_chars_vis]}..<{str_len}chars>.."
