"""Central logging configuration.

Sets up a formatter that prints timestamps in IST (UTC+5:30).
Import and call `setup_logging()` once at app startup.

Usage anywhere else in the codebase:
    import logging
    logger = logging.getLogger("your_module_name")
"""

import logging
import datetime


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

    if not root.handlers:
        root.addHandler(handler)
    else:
        root.handlers.clear()
        root.addHandler(handler)
