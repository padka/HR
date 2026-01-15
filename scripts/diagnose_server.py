#!/usr/bin/env python3
"""Diagnose server startup and notification system."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager
from backend.core.settings import get_settings
from backend.apps.admin_ui.state import setup_bot_state
from backend.apps.bot.services import get_bot, NotificationNotConfigured, get_notification_service
from fastapi import FastAPI


async def diagnose_server():
    """Diagnose server startup."""

    print("=" * 60)
    print("🔍 Server Startup Diagnostics")
    print("=" * 60)
    print()

    # Create minimal FastAPI app
    app = FastAPI()

    print("📋 Settings:")
    settings = get_settings()
    print(f"   Environment: {settings.environment}")
    print(f"   BOT_ENABLED: {settings.bot_enabled}")
    print(f"   BOT_AUTOSTART: {settings.bot_autostart}")
    print(f"   BOT_INTEGRATION_ENABLED: {settings.bot_integration_enabled}")
    print()

    print("🚀 Initializing bot state...")
    try:
        integration = await setup_bot_state(app)
        print(f"   ✅ Bot state initialized")
        print(f"      Integration: {integration}")
        print()

        # Check if bot is configured
        print("🤖 Checking bot configuration...")
        try:
            bot = get_bot()
            print(f"   ✅ Bot IS configured!")
            print(f"      Bot: {bot}")

            # Try to get bot info
            try:
                me = await bot.get_me()
                print(f"      Username: @{me.username}")
                print(f"      ID: {me.id}")
            except Exception as e:
                print(f"      ⚠️ Could not get bot info: {e}")

        except RuntimeError as e:
            print(f"   ❌ Bot NOT configured: {e}")

        print()

        # Check notification service
        print("📬 Checking notification service...")
        try:
            notification_service = get_notification_service()
            print(f"   ✅ Notification service IS configured")
            print(f"      Service: {notification_service}")
            print(f"      Running: {getattr(notification_service, '_started', 'unknown')}")

            # Check health
            try:
                health = notification_service.health_snapshot()
                print(f"      Health: {health}")
            except Exception as e:
                print(f"      ⚠️ Could not get health: {e}")

        except NotificationNotConfigured as e:
            print(f"   ❌ Notification service NOT configured: {e}")
        except RuntimeError as e:
            print(f"   ❌ Notification service error: {e}")

        print()

        # Cleanup
        await integration.shutdown()

    except Exception as e:
        print(f"   ❌ Error initializing bot state: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(diagnose_server())
