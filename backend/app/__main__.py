"""Launch Uvicorn bound only to the configured loopback host."""

from __future__ import annotations

import sys

import uvicorn

from .config import settings
from .main import _is_loopback


def main() -> None:
    host = (settings.host or "").strip()
    if not _is_loopback(host):
        print(
            f"Refusing to start: RECALL_HOST={host!r} is not loopback. "
            "Bind 127.0.0.1 / localhost / ::1 only.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    # Force the process bind to settings.host so a CLI --host 0.0.0.0 cannot bypass.
    uvicorn.run(
        "app.main:app",
        host=host,
        port=int(settings.port),
        reload=False,
    )


if __name__ == "__main__":
    main()
