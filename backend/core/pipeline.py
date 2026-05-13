"""Pipeline execution infrastructure.

Contains everything that wraps tool execution — timing, tracing, SSE streaming.
agent.py is the "what to run"; pipeline.py is the "how to run it".

Exports:
  tool_span       — async context manager: times a tool, logs it, emits SSE events
  run_agent_stream — async generator: runs run_agent and streams SSE events
  set_event_queue — activate streaming for the current async context
"""

import asyncio
import json
import logging
import time
import contextvars
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from models.response import ToolTrace

_logger = logging.getLogger("agent")

TOTAL_TOOLS = 5

# Holds the SSE event queue for the current request context.
# Set via set_event_queue(); tool_span reads it automatically.
_event_queue: contextvars.ContextVar[asyncio.Queue | None] = contextvars.ContextVar(
    "_event_queue", default=None
)


def set_event_queue(q: asyncio.Queue) -> contextvars.Token:
    """Activate streaming for the current async context. Returns a reset token."""
    return _event_queue.set(q)


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
    step: int = 0,
    thinking: str = "",
) -> AsyncGenerator[_Span, None]:
    """Times a tool, logs it, appends a ToolTrace, and emits SSE events.

    Usage:
        async with tool_span(trace, "my_tool", "input summary", step=2,
                             thinking="Fetching data...") as span:
            result = await run_tool(...)
            span.output = "what happened"
    """
    queue = _event_queue.get()
    label = f"[{step}/{TOTAL_TOOLS}] {name:<22}" if step else f"[{name}]"

    if queue and thinking:
        await queue.put({"type": "thinking", "step": step, "message": thinking})

    span = _Span()
    t0 = time.perf_counter()
    try:
        yield span
    except Exception as exc:
        span.error = str(exc)
        span.used_fallback = True
        ms = round((time.perf_counter() - t0) * 1000, 1)
        _logger.error(f"  {label}  ERROR: {exc}  ({ms}ms)")
        raise
    finally:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        if not span.error:
            _logger.info(f"  {label}  {span.output}  ({ms}ms)")
        trace.append(ToolTrace(
            tool_name=name,
            input_summary=input_summary,
            output_summary=span.output,
            duration_ms=ms,
            used_fallback=span.used_fallback,
            error=span.error,
        ))
        if queue:
            await queue.put({
                "type": "trace",
                "step": step,
                "tool_name": name,
                "output": span.output,
                "duration_ms": ms,
                "used_fallback": span.used_fallback,
                "error": span.error,
            })


async def run_agent_stream(user_input) -> AsyncGenerator[str, None]:
    """Run the agent and yield SSE-formatted strings as each tool progresses.

    Event types:
      {"type": "thinking", "step": N, "message": "..."}              before tool runs
      {"type": "trace",    "step": N, "tool_name": "...", ...}       after tool completes
      {"type": "result",   "plan": {...}}                             final plan
      {"type": "error",    "message": "..."}                         unrecoverable failure
    """
    from core.agent import run_agent  # local import to avoid circular dependency

    queue: asyncio.Queue = asyncio.Queue()
    token = set_event_queue(queue)

    async def _run() -> None:
        try:
            result = await run_agent(user_input)
            await queue.put({"type": "result", "plan": result.model_dump()})
        except Exception as exc:
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)  # sentinel — stream is done

    task = asyncio.create_task(_run())
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        if not task.done():
            task.cancel()
        _event_queue.reset(token)
