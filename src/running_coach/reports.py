from __future__ import annotations

from pathlib import Path


def write_text_report(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [f"# {title}", ""]
    body.extend(lines)
    path.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")
