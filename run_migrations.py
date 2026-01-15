#!/usr/bin/env python3
"""Apply database migrations to production/development database."""

from backend.migrations.runner import upgrade_to_head

if __name__ == "__main__":
    print("🔄 Applying database migrations...")
    try:
        upgrade_to_head()
        print("✅ Migrations applied successfully!")
    except Exception as e:
        print(f"❌ Error applying migrations: {e}")
        raise
