
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from backend.core.db import async_session
from backend.domain.models import MessageTemplate
from backend.apps.bot.templates import DEFAULT_TEMPLATES

async def main():
    print("Seeding default templates...")
    async with async_session() as session:
        seeded_count = 0
        for key, text in DEFAULT_TEMPLATES.items():
            # Check if exists (global)
            existing = await session.scalar(
                select(MessageTemplate).where(
                    MessageTemplate.key == key,
                    MessageTemplate.locale == "ru",
                    MessageTemplate.channel == "tg",
                    MessageTemplate.city_id.is_(None)
                )
            )
            
            if existing:
                continue
                
            # Convert text syntax if needed?
            # DEFAULT_TEMPLATES likely use python format syntax {var}.
            # We need to convert to {{ var }}.
            # Using logic from migrate_legacy_templates
            import re
            def repl(m):
                return "{{ " + m.group(1) + " }}"
            new_text = re.sub(r'(?<!\{)\{([a-zA-Z0-9_]+)\}(?!\})', repl, text)
            
            tmpl = MessageTemplate(
                key=key,
                locale="ru",
                channel="tg",
                body_md=new_text,
                version=1,
                is_active=True,
                city_id=None,
                description="Seeded from DEFAULT_TEMPLATES",
                updated_by="seed_script"
            )
            session.add(tmpl)
            seeded_count += 1
            print(f"Seeded {key}")
            
        await session.commit()
        print(f"Seeding finished. Added: {seeded_count}")

if __name__ == "__main__":
    asyncio.run(main())
