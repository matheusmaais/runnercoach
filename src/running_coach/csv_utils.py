from __future__ import annotations

import json
from typing import Any


def encode_json_cell(value: list[str] | list[dict[str, Any]]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def decode_json_cell(value: str | None) -> list[Any]:
    if value is None or value == "":
        return []
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        raise ValueError("CSV JSON cell must decode to a list")
    return decoded
