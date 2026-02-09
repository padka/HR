
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.db import async_session
from backend.domain.models import City

async def main():
    async with async_session() as session:
        # Create a city with intro template
        c = City(name="Test City", intro_day_template="Welcome to [City], {name}!", active=True)
        session.add(c)
        await session.commit()
        print("Seeded city.")

if __name__ == "__main__":
    asyncio.run(main())
