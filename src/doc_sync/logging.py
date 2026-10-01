from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def emit_log(level: str, message: str, **fields: Any) -> str:
    payload = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'level': level,
        'message': message,
        **fields,
    }
    return json.dumps(payload, sort_keys=True)


def summarize_run(run_result: dict[str, Any]) -> str:
    return json.dumps(run_result, sort_keys=True)
