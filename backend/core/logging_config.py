"""Central logging configuration.

Sets up a formatter that prints timestamps in IST (UTC+5:30).
Import and call `setup_logging()` once at app startup.

Also provides `tool_span` — an async context manager for timing, logging,
and trace-building around each pipeline tool.

Usage:
    import logging
    from core.logging_config import tool_span

    logger = logging.getLogger("your_module_name")

    async with tool_span(trace, "my_tool", "input summary") as span:
        result = await run_tool(...)
        span.output = "what happened"
        span.used_fallback = False
"""

import time
import logging
import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from models.response import ToolTrace


_span_logger = logging.getLogger("agent")


class ISTFormatter(logging.Formatter):
    """Logging formatter that converts timestamps to IST (UTC+5:30)."""

    IST_OFFSET = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ist_time = datetime.datetime.fromtimestamp(record.created, tz=self.IST_OFFSET)
        if datefmt:
            return ist_time.strftime(datefmt)
        return ist_time.strftime("%Y-%m-%d %H:%M:%S IST")


def setup_logging(level: int = logging.INFO) -> None:
    formatter = ISTFormatter(
        fmt="%(asctime)s | %(name)-12s | %(levelname)-5s | %(message)s",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


class _Span:
    """Mutable bag the caller fills in during a tool_span block."""
    output: str = ""
    used_fallback: bool = False
    error: str = ""


@asynccontextmanager
async def tool_span(
    trace: list[ToolTrace],
    name: str,
    input_summary: str = "",
) -> AsyncGenerator[_Span, None]:
    """Times a tool, logs start/end, appends a ToolTrace entry."""
    span = _Span()
    t0 = time.perf_counter()
    try:
        yield span
    except Exception as exc:
        span.error = str(exc)
        span.used_fallback = True
        ms = round((time.perf_counter() - t0) * 1000, 1)
        _span_logger.error(f"[{name}] ERROR: {exc} ({ms}ms)")
        raise
    finally:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        if not span.error:
            _span_logger.info(f"[{name}] {span.output} ({ms}ms)")
        trace.append(ToolTrace(
            tool_name=name,
            input_summary=input_summary,
            output_summary=span.output,
            duration_ms=ms,
            used_fallback=span.used_fallback,
            error=span.error,
        ))
