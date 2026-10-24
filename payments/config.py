"""
Reading ``config.toml``.

``load_config`` only parses the file; each module reads its own part:
``[llm]`` in ``language.py``, ``[policy]`` in ``policy.py``, and
``customer_file`` in ``bank_payment_service.py``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

# ===

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """The raw TOML tables (empty if the file is missing)"""

    if not path.exists():
        return {}

    with path.open("rb") as f:
        return tomllib.load(f)
