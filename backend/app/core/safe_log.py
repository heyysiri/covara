"""Logging helper that never writes document content.

A normal traceback includes the exception MESSAGE, and messages from validation or parsing errors often contain the
offending value (a name, an amount, a snippet of a document). For health documents that must not reach a log file.
This records only the exception type and where it happened (file, line, function).
"""

from __future__ import annotations

import traceback


def safe_trace(exc: BaseException, limit: int = 6) -> str:
    frames = traceback.extract_tb(exc.__traceback__)[-limit:]
    where = " <- ".join(f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno} in {f.name}" for f in reversed(frames))
    return f"{type(exc).__name__} at {where or 'unknown location'}"
