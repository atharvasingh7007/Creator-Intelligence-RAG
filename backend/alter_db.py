import asyncio
# pyrefly: ignore [missing-import]
from sqlalchemy import text
from app.services.metadata_db import get_session

async def alter():
    session = await get_session()
    async with session:
        await session.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS transcript_source VARCHAR(32) DEFAULT 'api'"))
        await session.commit()
        print("Success")

if __name__ == '__main__':
    asyncio.run(alter())
