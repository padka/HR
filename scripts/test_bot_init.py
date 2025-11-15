#!/usr/bin/env python3
"""Test bot initialization."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.settings import get_settings
from backend.apps.admin_ui.state import _build_bot


async def test_bot():
    """Test if bot can be initialized."""

    print("=" * 60)
    print("🤖 Testing Bot Initialization")
    print("=" * 60)
    print()

    settings = get_settings()

    print(f"Environment: {settings.environment}")
    print(f"BOT_ENABLED: {settings.bot_enabled}")
    print(f"BOT_PROVIDER: {settings.bot_provider}")
    print(f"BOT_TOKEN: {settings.bot_token[:20]}..." if settings.bot_token else "Not set")
    print(f"BOT_AUTOSTART: {settings.bot_autostart}")
    print(f"BOT_INTEGRATION_ENABLED: {settings.bot_integration_enabled}")
    print()

    print("Attempting to build bot...")
    try:
        bot, configured = _build_bot(settings)

        if configured:
            print(f"✅ Bot successfully configured!")
            print(f"   Bot object: {bot}")
            print(f"   Bot token: {bot.token[:20]}..." if bot and bot.token else "No token")

            # Try to get bot info
            if bot:
                try:
                    me = await bot.get_me()
                    print(f"   Bot username: @{me.username}")
                    print(f"   Bot ID: {me.id}")
                    print(f"   Bot name: {me.first_name}")
                except Exception as e:
                    print(f"   ⚠️ Could not get bot info: {e}")
        else:
            print(f"❌ Bot NOT configured")
            print(f"   Bot object: {bot}")

    except Exception as e:
        print(f"❌ Error building bot: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_bot())
