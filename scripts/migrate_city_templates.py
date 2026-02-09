
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from backend.core.db import async_session
from backend.domain.models import City, MessageTemplate

def convert_syntax(text: str) -> str:
    if not text:
        return ""
    text = text.replace("[Имя]", "{{ candidate_name }}")
    text = text.replace("[Candidate]", "{{ candidate_name }}")
    
    def repl(m):
        key = m.group(1)
        return "{{ " + key + " }}"

    text = re.sub(r'(?<!\{)\{([a-zA-Z0-9_]+)\}(?!\})', repl, text)
    return text

async def main():
    print("Starting migration of City intro_day_templates...")
    async with async_session() as session:
        result = await session.execute(select(City).where(City.intro_day_template.is_not(None)))
        cities = result.scalars().all()
        
        print(f"Found {len(cities)} cities with intro templates.")
        
        migrated_count = 0
        
        for city in cities:
            if not city.intro_day_template or not city.intro_day_template.strip():
                continue
                
            new_body = convert_syntax(city.intro_day_template)
            key = "intro_day_invite"
            
            existing = await session.scalar(
                select(MessageTemplate).where(
                    MessageTemplate.key == key,
                    MessageTemplate.locale == "ru",
                    MessageTemplate.channel == "tg",
                    MessageTemplate.city_id == city.id
                )
            )
            
            if existing:
                continue
            
            new_tmpl = MessageTemplate(
                key=key,
                locale="ru",
                channel="tg",
                body_md=new_body,
                version=1,
                is_active=True,
                city_id=city.id,
                description=f"Migrated intro day invite for {city.name}",
                updated_by="migration_script"
            )
            session.add(new_tmpl)
            migrated_count += 1
            
        await session.commit()
        print(f"City Migration finished. Migrated: {migrated_count}")

if __name__ == "__main__":
    asyncio.run(main())
