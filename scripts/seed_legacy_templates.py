
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.models import Template

async def main():
    async with async_session() as session:
        # Create a legacy template
        t1 = Template(key="test_legacy_1", content="Hello [Имя], your code is {code}", city_id=None)
        session.add(t1)
        await session.commit()
        print("Seeded legacy template.")

if __name__ == "__main__":
    asyncio.run(main())
