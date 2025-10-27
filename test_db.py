import asyncio
from sqlalchemy import text
from database import init_db, AsyncSessionLocal, engine


async def main():
    try:
        await init_db()  # опционально: создаст таблицы и проверит коннект
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT 1"))
            val = res.scalar_one()
            print("DB OK, SELECT 1 ->", val)
    except Exception as e:
        print("DB ERROR:", e)
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
