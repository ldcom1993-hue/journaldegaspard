from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def safe_write_non_empty_list(path: Path, payload: list[Any], minimum_items: int, label: str) -> None:
    if len(payload) < minimum_items:
        raise RuntimeError(f"Refusing to overwrite {label}: expected at least {minimum_items} items, got {len(payload)}")
    atomic_write_json(path, payload)
