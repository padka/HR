"""Entry point for VK Max bot webhook server.

Usage:
    python max_bot.py

Runs the Max bot as a standalone FastAPI service on port 8200.
"""

import os
import sys


def main() -> None:
    port = int(os.getenv("MAX_BOT_PORT", "8200"))
    host = os.getenv("MAX_BOT_HOST", "0.0.0.0")

    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required. Install with: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    uvicorn.run(
        "backend.apps.max_bot.app:create_app",
        factory=True,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
