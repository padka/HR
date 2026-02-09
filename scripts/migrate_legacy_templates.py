
import asyncio
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from backend.core.db import async_session
from backend.domain.models import Template, MessageTemplate

def convert_syntax(text: str) -> str:
    if not text:
        return ""
    # Replace [Имя] with {{ candidate_name }}
    text = text.replace("[Имя]", "{{ candidate_name }}")
    text = text.replace("[Candidate]", "{{ candidate_name }}")
    
    # Replace {var} with {{ var }}
    # Regex matches {word} ensuring it is not part of {{word}}
    # match {KEY} where KEY is alphanumeric/underscore
    
    def repl(m):
        key = m.group(1)
        # Map common legacy keys if they differ
        # (Assuming they match for now, or add mapping here)
        return "{{ " + key + " }}"

    # Pattern: Not preceded by {, {KEY}, not followed by }
    text = re.sub(r'(?<!\{)\{([a-zA-Z0-9_]+)\}(?!\})', repl, text)
    
    return text

async def main():
    print("Starting migration of legacy templates...")
    async with async_session() as session:
        # Get all legacy templates
        result = await session.execute(select(Template))
        legacy_templates = result.scalars().all()
        
        print(f"Found {len(legacy_templates)} legacy templates.")
        
        migrated_count = 0
        skipped_count = 0
        
        for tmpl in legacy_templates:
            new_body = convert_syntax(tmpl.content)
            
            # Check if exists (any version, any active state?)
            # We want to avoid duplicates if migration runs twice.
            # Check active one.
            existing = await session.scalar(
                select(MessageTemplate).where(
                    MessageTemplate.key == tmpl.key,
                    MessageTemplate.locale == "ru",
                    MessageTemplate.channel == "tg",
                    MessageTemplate.city_id == tmpl.city_id
                )
            )
            
            if existing:
                skipped_count += 1
                continue
                
            new_tmpl = MessageTemplate(
                key=tmpl.key,
                locale="ru",
                channel="tg",
                body_md=new_body,
                version=1,
                is_active=True,
                city_id=tmpl.city_id,
                description="Migrated from legacy templates",
                updated_by="migration_script"
            )
            session.add(new_tmpl)
            migrated_count += 1
            
        await session.commit()
        print(f"Migration finished. Migrated: {migrated_count}, Skipped: {skipped_count}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
