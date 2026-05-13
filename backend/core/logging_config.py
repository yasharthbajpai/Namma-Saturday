"""Logging configuration — IST formatter and one-time setup.

Call setup_logging() once at app startup (main.py).
All other modules just do: logger = logging.getLogger("name")
"""

import logging
import datetime


class ISTFormatter(logging.Formatter):
    """Logging formatter that prints timestamps in IST (UTC+5:30)."""

    IST_OFFSET = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ist_time = datetime.datetime.fromtimestamp(record.created, tz=self.IST_OFFSET)
        if datefmt:
            return ist_time.strftime(datefmt)
        return ist_time.strftime("%Y-%m-%d %H:%M:%S IST")


def setup_logging(level: int = logging.INFO) -> None:
    formatter = ISTFormatter(fmt="%(asctime)s  %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # httpx logs every HTTP request at INFO — silence to WARNING
    logging.getLogger("httpx").setLevel(logging.WARNING)
