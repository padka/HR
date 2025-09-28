#!/usr/bin/env python3
"""CLI wrapper to launch the recruitment Telegram bot."""

from __future__ import annotations

import asyncio
import logging

from backend.apps.bot import main


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")


if __name__ == "__main__":
    run()
