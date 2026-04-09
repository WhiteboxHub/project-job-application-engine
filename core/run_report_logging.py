"""
Append the post-run report (same payload as data/output.json) to a persistent log file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import settings
from core.logger import logger

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _execution_log_path() -> Path | None:
    raw = getattr(settings, "EXECUTION_LOG_FILE", None)
    if raw is None or not str(raw).strip():
        return None
    p = Path(str(raw).strip())
    return p if p.is_absolute() else _PROJECT_ROOT / p


def append_output_json_to_execution_log(
    report: dict[str, Any] | None,
    *,
    source_file: str = "data/output.json",
) -> None:
    """
    After each engine run, append a delimited block containing the full output.json
    document so it is visible in the execution log file on disk.
    """
    path = _execution_log_path()
    if path is None:
        return

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        sep = "=" * 60
        header = f"\n{sep}\nOUTPUT.JSON {ts} ({source_file})\n{sep}\n"
        body = json.dumps(report or {}, indent=2, ensure_ascii=False)
        footer = f"\n{sep}\nEND OUTPUT.JSON\n\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(header)
            f.write(body)
            f.write(footer)
        logger.info("Wrote run report (output.json payload) to execution log: %s", path)
    except OSError as e:
        logger.warning("Could not append output.json to execution log %s: %s", path, e)
