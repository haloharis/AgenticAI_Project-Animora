from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_env() -> None:
    load_dotenv()


def sanitize_filename(text: str, max_len: int = 50) -> str:
    sanitized = re.sub(r"[^\w\-_]", "_", text)
    return sanitized[:max_len].strip("_")


def ensure_dirs(*paths: str) -> None:
    for path in paths:
        os.makedirs(path, exist_ok=True)


def save_json(data: dict | list, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_json(path: str) -> dict | list:
    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ms_to_seconds(ms: int) -> float:
    return ms / 1000.0


def seconds_to_ms(s: float) -> int:
    return int(s * 1000)


def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def chunk_list(lst: list, size: int) -> List[list]:
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def retry(func: Callable, attempts: int = 3, delay: float = 1.0) -> Any:
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return func()
        except Exception as e:
            last_exc = e
            if i < attempts - 1:
                wait = delay * (2**i)
                logger.warning(f"Retry {i+1}/{attempts} after {wait}s: {e}")
                time.sleep(wait)
    raise last_exc  # type: ignore


def get_output_dir() -> str:
    return os.getenv("OUTPUT_DIR", "data/outputs")


def get_temp_dir() -> str:
    return os.getenv("TEMP_DIR", "data/temp")


def get_state_dir() -> str:
    return os.getenv("STATE_DIR", "data/state_versions")


def get_db_path() -> str:
    return os.getenv("SQLITE_DB_PATH", "data/animora.db")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
