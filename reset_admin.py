import asyncio
from sqlalchemy import delete
from app.database import AsyncSessionLocal
from app.models.db_models import User

async def reset_admin():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.username == "admin"))
        await db.commit()
        print("Admin user deleted. Restart the backend to recreate it.")

if __name__ == "__main__":
    asyncio.run(reset_admin())
