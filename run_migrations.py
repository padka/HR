#!/usr/bin/env python
"""Script to run database migrations."""

from backend.migrations.runner import upgrade_to_head

if __name__ == "__main__":
    print("Running database migrations...")
    upgrade_to_head()
    print("Migrations completed successfully!")
